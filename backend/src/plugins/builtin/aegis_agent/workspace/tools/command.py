"""命令执行工具——沙箱内安全执行 shell 命令。"""

import json
from typing import Any

from loguru import logger

from src.plugins.builtin.aegis_agent.workspace.sandbox import Sandbox, SandboxConfig


async def execute_command(
    project_root: str,
    command: str,
    cwd: str = ".",
    timeout: int = 60,
) -> str:
    """在沙箱内执行 shell 命令。

    Args:
        project_root: 项目根目录绝对路径
        command: 要执行的命令
        cwd: 工作目录（相对项目根），默认为根目录
        timeout: 超时秒数，默认 60
    """
    sandbox = Sandbox(SandboxConfig(
        root_path=project_root,
        enabled=True,
        timeout_seconds=timeout,
    ))

    result = await sandbox.execute(command, cwd=cwd)

    return json.dumps({
        "command": command,
        "exit_code": result.exit_code,
        "stdout": result.stdout[:5000],
        "stderr": result.stderr[:2000],
        "duration_ms": result.duration_ms,
        "blocked": result.blocked,
        "block_reason": result.block_reason if result.blocked else None,
    }, ensure_ascii=False)
