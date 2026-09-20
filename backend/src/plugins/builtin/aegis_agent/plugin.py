"""AegisCode Agent 插件入口类。"""

from typing import Any

from fastapi import FastAPI
from loguru import logger
from sqlalchemy import delete

from src.core.config import settings
from src.db import Base, SessionLocal
from src.plugins import Event, PluginInterface, event_bus
from src.plugins.builtin.aegis_agent.models import (  # noqa: F401 — register ORM metadata
    AgentCheckpoint,
    AgentEvent,
    AgentRun,
    AgentStep,
    AgentUsageLog,
)
from src.plugins.builtin.aegis_agent.seed import seed_aegis_agent_data


class AegisAgentPlugin(PluginInterface):
    """AegisCode Agent 运行时插件。

    核心能力:
    - 状态机驱动的对话循环
    - 精确 Token 计量（API usage 返回值，非粗估）
    - 分层上下文管理（压缩是视图不是删除）
    - 三重循环检测
    - 检查点/暂停/恢复
    """

    name = "aegis_agent"
    display_name = "AegisCode Agent"
    description = "AegisCode 核心 Agent 运行时——状态机驱动对话循环、精确 Token 计量、分层上下文管理"
    version = "0.1.0"
    author = "AegisCode"
    dependencies: tuple[str, ...] = ()

    def on_load(self) -> None:
        logger.info("[AegisAgent] loaded into memory")

    async def install(self) -> None:
        """创建表 + seed 菜单。"""
        from src.db import engine
        from src.models.mixins import IDMixin, TimestampMixin  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(
                    sync_conn,
                    tables=[
                        AgentRun.__table__,
                        AgentStep.__table__,
                        AgentUsageLog.__table__,
                        AgentEvent.__table__,
                        AgentCheckpoint.__table__,
                    ],
                )
            )

        async with SessionLocal() as db:
            await seed_aegis_agent_data(db)
            await db.commit()
        logger.info("[AegisAgent] installed — tables ready, menus seeded")

    async def uninstall(self) -> None:
        """删除表 + 清理菜单。"""
        async with SessionLocal() as db:
            from src.db import engine
            async with engine.begin() as conn:
                await conn.run_sync(
                    lambda sync_conn: Base.metadata.drop_all(
                        sync_conn,
                        tables=[
                            AgentCheckpoint.__table__,
                            AgentEvent.__table__,
                            AgentUsageLog.__table__,
                            AgentStep.__table__,
                            AgentRun.__table__,
                        ],
                    )
                )

            from src.models import Menu
            await db.execute(
                delete(Menu).where(Menu.permission.like("aegis_agent:%"))
            )
            await db.execute(
                delete(Menu).where(Menu.path == "/aegis-agent")
            )
            await db.commit()
        logger.info("[AegisAgent] uninstalled — tables dropped, menus removed")

    def register(self, app: FastAPI) -> None:
        """注册路由。"""
        from src.plugins.builtin.aegis_agent.api import router

        app.include_router(router, prefix=settings.API_PREFIX)

        # 订阅事件（示例：日志记录）
        event_bus.on(
            Event.USER_LOGIN,
            self._on_user_login,
            plugin_name=self.name,
        )
        logger.info("[AegisAgent] registered — routes + event subscription")

    def register_mcp_tools(self) -> None:
        """注册 MCP 工具。"""
        from src.plugins.builtin.aegis_agent.mcp_tools import register_aegis_agent_mcp_tools

        register_aegis_agent_mcp_tools()

    def unregister(self, app: FastAPI) -> None:
        logger.info("[AegisAgent] unregistered — runtime resources released")

    def on_unload(self) -> None:
        logger.info("[AegisAgent] unloaded from memory")

    async def _on_user_login(self, *args, **kwargs) -> None:
        user_id = kwargs.get("user_id", "unknown")
        logger.debug(f"[AegisAgent] user login: {user_id}")
