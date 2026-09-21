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
    """

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

        result = await self.sandbox.execute("git init", cwd=".")
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

    async def create_snapshot(
        self,
        project_id: int,
        run_id: int | None = None,
        step_index: int | None = None,
        commit_message: str = "auto snapshot",
    ) -> SnapshotInfo | None:
        """创建 Git 快照。"""
        if not await self.ensure_repo():
            return None

        # git add -A
        await self.sandbox.execute("git add -A", cwd=".")

        # 检查是否有变更
        status_result = await self.sandbox.execute("git status --porcelain", cwd=".")
        if not status_result.stdout.strip():
            logger.debug("No changes to snapshot")
            return None

        # git commit
        safe_msg = commit_message.replace('"', '\\"')
        commit_result = await self.sandbox.execute(
            f'git commit -m "{safe_msg}" --allow-empty',
            cwd=".",
        )
        if commit_result.exit_code != 0:
            logger.error(f"Git commit failed: {commit_result.stderr}")
            return None

        # 获取 commit hash
        hash_result = await self.sandbox.execute("git rev-parse HEAD", cwd=".")
        commit_hash = hash_result.stdout.strip()

        # 获取变更文件列表（修复: 首次 commit 无 HEAD~1 会失败，
        # 先检测 commit 数量，只有 1 个 commit 时用 git show --name-only）
        count_result = await self.sandbox.execute(
            "git rev-list --count HEAD", cwd="."
        )
        commit_count = int(count_result.stdout.strip() or "0")
        if commit_count > 1:
            diff_result = await self.sandbox.execute(
                "git diff --name-only HEAD~1 HEAD", cwd="."
            )
        else:
            diff_result = await self.sandbox.execute(
                "git show --name-only --format= HEAD", cwd="."
            )
        files_changed = [
            f.strip() for f in diff_result.stdout.strip().split("\n")
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
                f"git diff {h}~1 {h}", cwd="."
            )
        else:
            result = await self.sandbox.execute("git diff", cwd=".")
        return result.stdout

    async def rollback(self, commit_hash: str) -> bool:
        """回滚到指定快照。"""
        # 修复: commit_hash 来自 DB/用户输入，防止 shell 注入（如 "; rm -rf"）
        if not re.fullmatch(r"[0-9a-fA-F]{4,40}", commit_hash.strip()):
            logger.error(f"Invalid commit hash rejected: {commit_hash!r}")
            return False
        result = await self.sandbox.execute(
            f"git checkout {commit_hash.strip()} -- .", cwd="."
        )
        if result.exit_code != 0:
            logger.error(f"Git rollback failed: {result.stderr}")
            return False
        logger.info(f"Rolled back to: {commit_hash[:8]}")
        return True

    async def list_snapshots(self, project_id: int) -> list[dict]:
        """列出项目的所有快照。"""
        async with SessionLocal() as db:
            stmt = (
                select(WorkspaceSnapshot)
                .where(WorkspaceSnapshot.project_id == project_id)
                .order_by(WorkspaceSnapshot.id.desc())
            )
            items = (await db.execute(stmt)).scalars().all()
        return [
            {
                "id": s.id,
                "commit_hash": s.commit_hash,
                "commit_message": s.commit_message,
                "run_id": s.run_id,
                "step_index": s.step_index,
                "reviewed": s.reviewed,
                "review_status": s.review_status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in items
        ]
