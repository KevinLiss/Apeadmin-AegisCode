"""AegisCode 工作区数据模型。

表名前缀: ``aegis_workspace_*``

核心表:
- aegis_workspace_projects     项目
- aegis_workspace_files         文件（虚拟文件系统）
- aegis_workspace_snapshots     Git 快照
- aegis_workspace_executions    命令执行记录
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    pass


class WorkspaceProject(IDMixin, TimestampMixin, Base):
    """工作区项目。

    一个项目对应一个代码工作区，包含文件树和 Git 历史。
    """

    __tablename__ = "aegis_workspace_projects"

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="创建者")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="项目名")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 文件系统
    root_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="项目根目录（绝对路径）"
    )

    # Git
    git_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用 Git 快照"
    )
    git_branch: Mapped[str] = mapped_column(
        String(100), nullable=False, default="main", comment="当前分支"
    )

    # 沙箱配置
    sandbox_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用沙箱"
    )
    allowed_paths: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="允许访问的路径列表(JSON)"
    )
    blocked_commands: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="禁止执行的命令列表(JSON)"
    )

    # 状态
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
        comment="active/archived/deleted",
    )

    def __repr__(self) -> str:
        return f"<WorkspaceProject {self.id} name={self.name}>"


class WorkspaceFile(IDMixin, TimestampMixin, Base):
    """工作区文件（虚拟文件系统元数据）。

    实际文件内容存储在磁盘上，此表仅维护元数据。
    """

    __tablename__ = "aegis_workspace_files"

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aegis_workspace_projects.id"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="相对项目根的路径"
    )
    is_directory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 文件信息
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="字节")
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="内容哈希(MD5)"
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="编程语言"
    )

    # 状态
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="normal",
        comment="normal/modified/deleted/new",
    )

    def __repr__(self) -> str:
        return f"<WorkspaceFile {self.id} path={self.path}>"


class WorkspaceSnapshot(IDMixin, TimestampMixin, Base):
    """Git 快照——Agent 每次修改文件后自动创建。

    对标 AegisCode 原实现 git_snapshot，保留快照 + 审阅机制。
    """

    __tablename__ = "aegis_workspace_snapshots"

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aegis_workspace_projects.id"), nullable=False, index=True
    )
    run_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="关联 Agent 运行ID"
    )
    step_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Git 信息
    commit_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="Git commit SHA"
    )
    commit_message: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", comment="提交信息"
    )
    files_changed: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="变更文件列表(JSON)"
    )

    # 审阅
    reviewed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否已审阅"
    )
    review_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="approved/rejected/pending"
    )
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<WorkspaceSnapshot {self.id} project={self.project_id}>"


class WorkspaceExecution(IDMixin, TimestampMixin, Base):
    """命令执行记录——沙箱内执行的命令及其结果。"""

    __tablename__ = "aegis_workspace_executions"

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aegis_workspace_projects.id"), nullable=False, index=True
    )
    run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # 命令
    command: Mapped[str] = mapped_column(Text, nullable=False, comment="执行的命令")
    cwd: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="工作目录"
    )

    # 结果
    exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 安全
    blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否被沙箱拦截"
    )
    block_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<WorkspaceExecution {self.id} cmd={self.command[:50]}>"
