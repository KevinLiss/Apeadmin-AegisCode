"""技能中心模型：Skill（技能）+ ToolConfig（全局工具清单）。

表名前缀: ``aegis_skill_*``
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    pass


class Skill(IDMixin, TimestampMixin, Base):
    """技能 — 可在 Agent 对话中调用的预定义能力。

    同名技能可按 user_id 隔离（null=系统内置全局技能）。
    """

    __tablename__ = "aegis_skills"

    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="所属用户ID，null=系统内置"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="技能名称(同用户下唯一)")
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="前端显示名")
    description: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", comment="技能描述"
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="general",
        comment="分类: general/code/search/document/custom/language",
    )
    skill_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="builtin",
        comment="builtin(自研) / imported(导入开源) / market(广场安装)",
    )
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="⚡", comment="图标")
    system_prompt: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="激活技能后注入的 system prompt"
    )
    tools: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", comment="可调用的工具名(JSON数组)"
    )
    params_schema: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", comment="用户使用技能时需填写的参数定义(JSON数组)"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    in_market: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否上架到技能广场"
    )
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="审核状态: pending/approved/rejected",
    )
    review_comment: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="审核备注")
    tool_sources: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]",
        comment="工具源码配置(JSON数组: [{name, description, source_code, source_file}])",
    )
    source_skill_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="来源技能ID(从广场安装时记录)"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")

    def __repr__(self) -> str:
        return f"<Skill {self.id} {self.name}>"


class ToolConfig(IDMixin, TimestampMixin, Base):
    """可用工具配置 — 管理中心维护的全局工具清单。"""

    __tablename__ = "aegis_tool_configs"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="工具唯一名称")
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="前端显示名")
    description: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", comment="工具描述"
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general", comment="分类")
    tool_sources: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]",
        comment="工具源码配置(JSON数组: [{name, description, source_code, source_file}])",
    )
    params_schema: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="参数定义(JSON数组)")
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="custom",
        comment="来源: builtin=内置, custom=自定义, mcp=MCP远程",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    is_readonly: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="内置工具只读，不可删除/编辑"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")

    def __repr__(self) -> str:
        return f"<ToolConfig {self.id} {self.name}>"
