"""MCP 服务器管理模型。

表名: ``aegis_mcp_servers``
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    pass


class McpServer(IDMixin, TimestampMixin, Base):
    """MCP 服务器配置 — 管理中心维护的 MCP 工具服务器。"""

    __tablename__ = "aegis_mcp_servers"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="服务器唯一名称")
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="前端显示名")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="描述")
    server_url: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="MCP 服务器地址")
    server_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="sse",
        comment="连接方式: sse / stdio / streamable_http",
    )
    api_key_enc: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="认证密钥(加密存储)"
    )
    tools: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]",
        comment="服务器提供的工具清单(JSON数组: [{name, description, params}])",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")

    def __repr__(self) -> str:
        return f"<McpServer {self.id} {self.name}>"
