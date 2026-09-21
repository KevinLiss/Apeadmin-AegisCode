"""AegisCode Git 快照管理。

Agent 每次修改文件后自动创建 Git 快照，支持审阅和回滚。
"""

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Any

from loguru import logger
from sqlalchemy import select

from src.db import SessionLocal
from src.plugins.builtin.aegis_agent.workspace.models import WorkspaceSnapshot
from src.plugins.builtin.aegis_agent.workspace.sandbox import Sandbox, SandboxConfig


@dataclass
class SnapshotInfo:
    """快照信息。"""
    commit_hash: str
    commit_message: str
    files_changed: list[str]


class GitManager:
    """Git 快照管理器。

    功能:
    1. 自动 init: 项目目录如果没有 .git，自动初始化
    2. 创建快照: git add + git commit
    3. 查看差异: git diff
    4. 回滚: git checkout

    注意: 所有 git 命令带 -c core.quotepath=false，
    防止中文/Unicode 文件名被转义成八进制（如 "AI\347\224\237...")。
    """

    GIT_PREFIX = "git -c core.quotepath=false"

    def __init__(self, root_path: str):
        self.root_path = root_path
        self.sandbox = Sandbox(SandboxConfig(
            root_path=root_path,
            enabled=True,
            timeout_seconds=30,
        ))

    async def ensure_repo(self) -> bool:
        """确保 Git 仓库存在，不存在则初始化。"""
        git_dir = os.path.join(self.root_path, ".git")
        if os.path.exists(git_dir):
            return True

        result = await self.sandbox.execute(f"{self.GIT_PREFIX} init", cwd=".")
        if result.exit_code != 0:
            logger.error(f"Git init failed: {result.stderr}")
            return False

        # 设置默认配置
        await self.sandbox.execute(
            'git config user.email "agent@aegiscode.ai"', cwd="."
        )
        await self.sandbox.execute(
            'git config user.name "AegisCode Agent"', cwd="."
        )
        logger.info(f"Git repo initialized: {self.root_path}")
        return True

    async def has_uncommitted_changes(self) -> bool:
        """检查工作区是否有未提交变更。"""
        if not await self.ensure_repo():
            return False
        result = await self.sandbox.execute(
            f"{self.GIT_PREFIX} status --porcelain", cwd="."
        )
        return bool(result.stdout.strip())

    async def create_snapshot(
        self,
        project_id: int,
        run_id: int | None = None,
        step_index: int | None = None,
        commit_message: str = "auto snapshot",
    ) -> SnapshotInfo | None:
        """创建 Git 快照。无变更时返回 None。"""
        if not await self.ensure_repo():
            return None

        # git add -A
        await self.sandbox.execute(f"{self.GIT_PREFIX} add -A", cwd=".")

        # 检查是否有变更（--allow-empty 已移除，无变更直接跳过，不再产生空提交）
        status_result = await self.sandbox.execute(
            f"{self.GIT_PREFIX} status --porcelain", cwd="."
        )
        if not status_result.stdout.strip():
            logger.debug("No changes to snapshot")
            return None

        # git commit
        safe_msg = commit_message.replace('"', '\\"')
        commit_result = await self.sandbox.execute(
            f'{self.GIT_PREFIX} commit -m "{safe_msg}"',
            cwd=".",
        )
        if commit_result.exit_code != 0:
            logger.error(f"Git commit failed: {commit_result.stderr}")
            return None

        # 获取 commit hash
        hash_result = await self.sandbox.execute(
            f"{self.GIT_PREFIX} rev-parse HEAD", cwd="."
        )
        commit_hash = hash_result.stdout.strip()

        # 获取变更文件列表（首 commit 无 HEAD~1，用 git show --name-only）
        count_result = await self.sandbox.execute(
            f"{self.GIT_PREFIX} rev-list --count HEAD", cwd="."
        )
        commit_count = int(count_result.stdout.strip() or "0")
        if commit_count > 1:
            diff_result = await self.sandbox.execute(
                f"{self.GIT_PREFIX} diff --name-only HEAD~1 HEAD", cwd="."
            )
        else:
            diff_result = await self.sandbox.execute(
                f"{self.GIT_PREFIX} show --name-only --format= HEAD", cwd="."
            )
        files_changed = [
            f.strip().strip('"') for f in diff_result.stdout.strip().split("\n")
            if f.strip()
        ] if diff_result.stdout.strip() else []

        # 持久化快照记录
        async with SessionLocal() as db:
            snapshot = WorkspaceSnapshot(
                project_id=project_id,
                run_id=run_id,
                step_index=step_index,
                commit_hash=commit_hash,
                commit_message=commit_message,
                files_changed=json.dumps(files_changed, ensure_ascii=False),
            )
            db.add(snapshot)
            await db.commit()
            await db.refresh(snapshot)

        logger.info(
            f"Snapshot created: project={project_id} commit={commit_hash[:8]} "
            f"files={len(files_changed)}"
        )
        return SnapshotInfo(
            commit_hash=commit_hash,
            commit_message=commit_message,
            files_changed=files_changed,
        )

    async def get_diff(self, commit_hash: str | None = None) -> str:
        """获取差异内容。"""
        if commit_hash:
            # 防 shell 注入: hash 必须是 4-40 位十六进制
            if not re.fullmatch(r"[0-9a-fA-F]{4,40}", commit_hash.strip()):
                logger.error(f"Invalid commit hash rejected: {commit_hash!r}")
                return ""
            h = commit_hash.strip()
            result = await self.sandbox.execute(
                f"{self.GIT_PREFIX} diff {h}~1 {h}", cwd="."
            )
        else:
            result = await self.sandbox.execute(f"{self.GIT_PREFIX} diff", cwd=".")
        return result.stdout

    async def rollback(self, commit_hash: str) -> tuple[bool, list[str]]:
        """回滚到指定快照（保留历史，可再次回滚回来）。

        实现（三步走，确保回滚彻底）:
        1. 删除「当前被跟踪但快照中不存在」的文件
           （checkout hash -- . 只恢复快照内文件，不会删除快照后新增的）
        2. git checkout <hash> -- . 恢复快照内容（处理修改/删除）
        3. 提交回滚 commit（不 reset 历史，可再回滚回来）

        快照后新增但已提交的文件由步骤 1 删除；
        快照后新增未提交（untracked）的文件由 checkout 前的 add -A + 步骤 1 覆盖
        （API 层回滚前会先建备份快照兜底）。
        """
        # 防 shell 注入: hash 必须是 4-40 位十六进制
        if not re.fullmatch(r"[0-9a-fA-F]{4,40}", commit_hash.strip()):
            logger.error(f"Invalid commit hash rejected: {commit_hash!r}")
            return False, ["无效的 commit hash"]
        h = commit_hash.strip()

        if not await self.ensure_repo():
            return False, ["Git 仓库初始化失败"]

        # 收集回滚前的工作区状态（受影响文件 = 修改 + 新增）
        status_before = await self.sandbox.execute(
            f"{self.GIT_PREFIX} status --porcelain", cwd="."
        )
        affected: list[str] = []
        for line in status_before.stdout.strip().split("\n"):
            if line.strip():
                p = line[3:].strip().strip('"')
                if p:
                    affected.append(p)

        # 1) 删除「被跟踪但快照中不存在」的文件
        #    comm --nosymref: 列出当前 HEAD 有而目标快照没有的路径
        removed = await self.sandbox.execute(
            f"{self.GIT_PREFIX} ls-tree -r --name-only HEAD", cwd="."
        )
        snap_tree = await self.sandbox.execute(
            f"{self.GIT_PREFIX} ls-tree -r --name-only {h}", cwd="."
        )
        current_files = {l.strip().strip('"') for l in removed.stdout.split("\n") if l.strip()}
        snap_files = {l.strip().strip('"') for l in snap_tree.stdout.split("\n") if l.strip()}
        extra_files = current_files - snap_files
        for f in extra_files:
            await self.sandbox.execute(
                f'{self.GIT_PREFIX} rm -f -- "{f}"', cwd="."
            )
            if f not in affected:
                affected.append(f)

        # 2) 恢复快照内容（修改/删除的文件）
        result = await self.sandbox.execute(
            f"{self.GIT_PREFIX} checkout {h} -- .", cwd="."
        )
        if result.exit_code != 0:
            logger.error(f"Git rollback failed: {result.stderr}")
            return False, [result.stderr.strip()[:200] or "回滚失败"]

        # 3) 提交回滚记录（含来源 hash，便于追溯）
        await self.sandbox.execute(f"{self.GIT_PREFIX} add -A", cwd=".")
        commit_result = await self.sandbox.execute(
            f'{self.GIT_PREFIX} commit -m "rollback to {h[:8]}"',
            cwd=".",
        )
        if commit_result.exit_code != 0:
            # 无变更也视为回滚成功（内容已一致）
            logger.debug(f"Rollback commit skipped: {commit_result.stderr}")

        logger.info(f"Rolled back to: {h[:8]} ({len(affected)} files affected)")
        return True, affected

    async def list_snapshots(self, project_id: int) -> list[dict]:
        """列出项目的所有快照。"""
        async with SessionLocal() as db:
            stmt = (
                select(WorkspaceSnapshot)
                .where(WorkspaceSnapshot.project_id == project_id)
                .order_by(WorkspaceSnapshot.id.desc())
            )
            items = (await db.execute(stmt)).scalars().all()
        def _utc_isoformat(dt) -> str | None:
            """SQLite 存的 naive UTC，补 Z 后缀让前端 new Date() 正确转本地时区。"""
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.isoformat() + "Z"
            return dt.isoformat()

        return [
            {
                "id": s.id,
                "commit_hash": s.commit_hash,
                "commit_message": s.commit_message,
                "run_id": s.run_id,
                "step_index": s.step_index,
                "files_changed": json.loads(s.files_changed) if s.files_changed else [],
                "files_count": len(json.loads(s.files_changed)) if s.files_changed else 0,
                "reviewed": s.reviewed,
                "review_status": s.review_status,
                "created_at": _utc_isoformat(s.created_at),
            }
            for s in items
        ]
