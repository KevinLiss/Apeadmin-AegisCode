"""项目成员模型：WorkspaceProjectMember。

表名: ``aegis_workspace_members``

对标旧项目 ProjectMember：
- 项目与用户的关联表
- role: viewer / member / developer / admin（owner 由项目 user_id 隐含，不落表）
- permissions: 项目级权限点数组（如 project:read, project:write, tool:execute）
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    pass


class WorkspaceProjectMember(IDMixin, TimestampMixin, Base):
    """项目成员 — 工作区项目与用户的关联。

    一个 (project_id, user_id) 唯一。
    owner 不在此表，由 WorkspaceProject.user_id 隐含。
    """

    __tablename__ = "aegis_workspace_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aegis_workspace_projects.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="成员用户ID")
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="member",
        comment="成员角色: viewer/member/developer/admin",
    )
    permissions: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]",
        comment="项目级权限点(JSON数组, 如 project:read/project:write/tool:execute)",
    )

    def __repr__(self) -> str:
        return f"<WorkspaceProjectMember project={self.project_id} user={self.user_id} role={self.role}>"


# 角色定义（供 API 校验与前端展示）
MEMBER_ROLES = {
    "viewer": "访客 — 只能查看项目内容",
    "member": "成员 — 可查看和编辑文件",
    "developer": "开发者 — 可编辑文件和执行命令",
    "admin": "管理员 — 可管理成员和全部操作",
}

# 角色对应的默认权限点
ROLE_DEFAULT_PERMISSIONS = {
    "viewer": ["project:read"],
    "member": ["project:read", "project:write"],
    "developer": ["project:read", "project:write", "tool:execute", "tool:git"],
    "admin": ["project:read", "project:write", "tool:execute", "tool:git", "member:manage"],
}

# 所有可分配的权限点
AVAILABLE_PERMISSIONS = [
    ("project:read", "查看项目 — 浏览文件树和读取文件"),
    ("project:write", "编辑项目 — 写入和修改文件"),
    ("tool:execute", "执行命令 — 在沙箱中运行命令"),
    ("tool:git", "Git 快照 — 创建和审阅快照"),
    ("member:manage", "成员管理 — 添加/修改/移除项目成员"),
]
