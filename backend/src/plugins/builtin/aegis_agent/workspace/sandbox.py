"""AegisCode 沙箱——路径/命令/资源约束。

保留 AegisCode 原实现的安全边界设计，简化为:
1. 路径约束: 只允许在项目根目录内操作
2. 命令黑名单: 禁止危险命令（rm -rf /, shutdown, 等）
3. 资源限制: 超时 + 输出截断
"""

import asyncio
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


# ---------------------------------------------------------------------------
# 危险命令黑名单
# ---------------------------------------------------------------------------

DANGEROUS_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\s+-rf\s+/(?:\s|$)"),         # rm -rf /
    re.compile(r"\brm\s+-rf\s+~"),                  # rm -rf ~
    re.compile(r"\bshutdown\b"),                    # shutdown
    re.compile(r"\breboot\b"),                      # reboot
    re.compile(r"\bmkfs\b"),                        # mkfs
    re.compile(r"\bdd\s+.*of=/dev/"),               # dd to device
    re.compile(r">\s*/dev/sd"),                     # write to disk device
    re.compile(r"\bchmod\s+-R\s+777\s+/(?:\s|$)"),  # chmod -R 777 /
    re.compile(r"\bcurl\s+.*\|\s*sh"),              # curl | sh
    re.compile(r"\bwget\s+.*\|\s*sh"),              # wget | sh
    # fork bomb（修复: 原 `\b:()\s*{...}` 中 `()` 是正则分组不匹配字面量，
    # 且漏了第二个冒号。实际写法 `:(){ :|:& };:` = 函数名 : 递归管道+后台）
    re.compile(r":\(\)\s*\{[^}]*\}\s*;\s*:"),
]

# 中危命令清单——不直接拦截，但需要用户人工确认后才会执行。
# 这些命令本身可能造成不可逆影响（删除/强制推送/重写历史等），
# 在自动化 Agent 场景中必须经用户批准。
CONFIRM_REQUIRED_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\s+-rf\b"),                    # rm -rf 相对路径（绝对路径已被高危拦截）
    re.compile(r"\brm\s+-r\b"),                     # rm -r 递归删除
    re.compile(r"\bgit\s+push\s+.*(--force|-f\b)"),  # git push --force
    re.compile(r"\bgit\s+reset\s+--hard"),          # git reset --hard
    re.compile(r"\bgit\s+clean\s+-fd"),             # git clean -fd
    re.compile(r"\bgit\s+branch\s+-D\b"),           # git branch -D
    re.compile(r"\bgit\s+checkout\s+--force"),      # git checkout --force
    re.compile(r"\b(pip|pip3)\s+uninstall\b"),      # pip uninstall
    re.compile(r"\b(pip|pip3)\s+install\s+--force"),# pip install --force
    re.compile(r"\bnpm\s+(uninstall|rm)\s+-g"),     # npm uninstall -g
    re.compile(r"\bnpm\s+publish\b"),               # npm publish
    re.compile(r"\bdrop\s+table\b", re.IGNORECASE),  # drop table
    re.compile(r"\balter\s+table\b", re.IGNORECASE), # alter table
    re.compile(r"\bdelete\s+from\b", re.IGNORECASE), # delete from
    re.compile(r"\bkill\s+-9\b"),                   # kill -9
    re.compile(r"\bpkill\s+-9\b"),                  # pkill -9
    re.compile(r"\bdocker\s+(rm|rmi|system\s+prune)\b"),  # docker 删除
    re.compile(r"\bsudo\b"),                        # sudo
    re.compile(r"\bdrop\s+database\b", re.IGNORECASE),    # drop database
    re.compile(r"\bchmod\s+-R\s+777\b"),            # chmod -R 777 非根目录
    re.compile(r"\bgit\s+config\s+--global"),       # git config --global
    re.compile(r"\bshred\b"),                       # shred 覆写删除
    re.compile(r"\bdd\b"),                          # dd（除已拦截的 of=/dev/ 外）
    re.compile(r"\bcurl\s+.*\|\s*(\bbash\b|\bsudo\b)"),  # curl | bash / sudo
    re.compile(r"\bmysql\s+.*-e\b"),                # mysql -e 直连执行
    re.compile(r"\bpsql\s+.*-c\b"),                 # psql -c 直连执行
]

# 允许的命令前缀（白名单模式可选）
SAFE_COMMANDS: set[str] = {
    "ls", "cat", "head", "tail", "grep", "find", "wc", "sort", "uniq",
    "diff", "tree", "echo", "pwd", "whoami", "date", "env",
    "python", "python3", "pip", "pip3", "node", "npm", "npx", "yarn",
    "git", "rg", "fd", "jq", "sed", "awk", "tr", "cut", "xargs",
    "mkdir", "cp", "mv", "touch", "chmod", "chown",
    "docker", "docker-compose",
    "curl", "wget",
    "ssh", "scp",
    "tar", "zip", "unzip", "gzip", "gunzip",
    "ps", "kill", "top", "df", "du", "free",
    "pytest", "unittest", "ruff", "flake8", "mypy", "eslint", "tsc",
    "vue-tsc", "vite", "webpack",
    "go", "cargo", "rustc",
    "java", "javac", "mvn", "gradle",
    "sqlite3", "mysql", "psql", "redis-cli",
}


@dataclass
class SandboxConfig:
    """沙箱配置。"""
    root_path: str = ""
    enabled: bool = True
    allowed_paths: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=list)
    timeout_seconds: int = 60
    max_output_chars: int = 50000
    use_whitelist: bool = False  # True=白名单模式, False=黑名单模式


@dataclass
class ExecutionResult:
    """命令执行结果。"""
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    blocked: bool = False
    block_reason: str = ""
    needs_approval: bool = False  # True=命中中危清单，需用户人工确认后才执行
    approval_reason: str = ""     # 需要审批的原因


class Sandbox:
    """沙箱执行环境。

    职责:
    1. 路径校验: 确保所有文件操作在项目根目录内
    2. 命令校验: 拦截危险命令
    3. 执行命令: 带超时和输出截断
    """

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._root = Path(config.root_path).resolve()

    # -----------------------------------------------------------------
    # 路径校验
    # -----------------------------------------------------------------

    def validate_path(self, path: str) -> tuple[bool, str]:
        """验证路径是否在项目根目录内。

        Returns:
            (is_valid, resolved_path or reason)
        """
        try:
            target = (self._root / path).resolve()
            # 检查是否在 root 内
            if not str(target).startswith(str(self._root)):
                return False, f"路径越界: {path} 不在项目根目录 {self._root} 内"

            # 检查额外允许的路径
            if self.config.allowed_paths:
                allowed = any(
                    str(target).startswith(str(Path(p).resolve()))
                    for p in self.config.allowed_paths
                )
                if not allowed and not str(target).startswith(str(self._root)):
                    return False, f"路径不在允许列表内: {path}"

            return True, str(target)
        except Exception as e:
            return False, f"路径解析失败: {e}"

    # -----------------------------------------------------------------
    # 命令校验
    # -----------------------------------------------------------------

    def validate_command(self, command: str) -> tuple[bool, str, bool]:
        """验证命令是否安全。

        Returns:
            (is_safe, reason_if_blocked, needs_confirmation)
            - is_safe=False 表示命令被直接拦截（高危黑名单）
            - needs_confirmation=True 表示命令命中中危清单，需用户人工确认
        """
        if not command.strip():
            return False, "空命令", False

        # 1. 检查用户自定义黑名单
        for blocked in self.config.blocked_commands:
            if blocked in command:
                return False, f"命令被黑名单拦截: 匹配 '{blocked}'", False

        # 2. 检查危险模式（高危——直接拦截）
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(command):
                return False, f"命令匹配危险模式: {pattern.pattern[:50]}", False

        # 2.5 检查中危清单（需人工确认）
        for pattern in CONFIRM_REQUIRED_PATTERNS:
            if pattern.search(command):
                return True, f"命令命中需人工确认模式: {pattern.pattern[:50]}", True

        # 3. 白名单模式：检查命令前缀
        if self.config.use_whitelist:
            try:
                parts = shlex.split(command)
                if parts and parts[0] not in SAFE_COMMANDS:
                    return False, f"命令 '{parts[0]}' 不在白名单中", False
            except ValueError:
                return False, "命令解析失败", False

        return True, "", False

    # -----------------------------------------------------------------
    # 执行命令
    # -----------------------------------------------------------------

    async def execute(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        skip_confirmation: bool = False,
    ) -> ExecutionResult:
        """在沙箱内执行命令。

        流程:
        1. 校验命令安全性（高危直接拦截；中危返回 needs_approval）
        2. 校验工作目录
        3. 执行（带超时）
        4. 截断输出

        Args:
            command: 要执行的命令
            cwd: 工作目录（相对项目根）
            env: 额外环境变量
            skip_confirmation: True=跳过中危确认清单（仅限用户已批准后由 runtime 调用）
        """
        import time

        start = time.time()

        # 校验命令
        is_safe, reason, needs_confirmation = self.validate_command(command)
        if needs_confirmation and not skip_confirmation:
            logger.warning(f"Sandbox needs approval for command: {command[:100]} — {reason}")
            return ExecutionResult(
                needs_approval=True,
                approval_reason=reason,
                duration_ms=int((time.time() - start) * 1000),
            )
        if not is_safe:
            logger.warning(f"Sandbox blocked command: {command[:100]} — {reason}")
            return ExecutionResult(
                blocked=True, block_reason=reason,
                duration_ms=int((time.time() - start) * 1000),
            )

        # 校验工作目录
        work_dir = self._root
        if cwd:
            valid, result = self.validate_path(cwd)
            if not valid:
                return ExecutionResult(
                    blocked=True, block_reason=f"工作目录无效: {result}",
                    duration_ms=int((time.time() - start) * 1000),
                )
            work_dir = Path(result)

        # 合并环境变量
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(work_dir),
                env=exec_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_seconds,
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # 截断输出
            truncated = False
            if len(stdout) > self.config.max_output_chars:
                stdout = stdout[:self.config.max_output_chars] + "\n... [输出已截断]"
                truncated = True
            if len(stderr) > self.config.max_output_chars:
                stderr = stderr[:self.config.max_output_chars] + "\n... [输出已截断]"
                truncated = True

            return ExecutionResult(
                exit_code=proc.returncode or 0,
                stdout=stdout,
                stderr=stderr,
                duration_ms=int((time.time() - start) * 1000),
            )

        except asyncio.TimeoutError:
            return ExecutionResult(
                exit_code=-1,
                stderr=f"命令超时（{self.config.timeout_seconds}秒）",
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            return ExecutionResult(
                exit_code=-1,
                stderr=str(e),
                duration_ms=int((time.time() - start) * 1000),
            )
