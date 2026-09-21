"""AegisCode 工作区插件入口类。"""

from fastapi import FastAPI
from loguru import logger
from sqlalchemy import delete

from src.core.config import settings
from src.db import Base, SessionLocal
from src.plugins import Event, PluginInterface, event_bus
from src.plugins.builtin.aegis_workspace.models import (  # noqa: F401
    WorkspaceExecution,
    WorkspaceFile,
    WorkspaceProject,
    WorkspaceSnapshot,
)
from src.plugins.builtin.aegis_workspace.member_models import (  # noqa: F401
    WorkspaceProjectMember,
)
from src.plugins.builtin.aegis_workspace.seed import seed_aegis_workspace_data


class AegisWorkspacePlugin(PluginInterface):
    """AegisCode 工作区插件。

    核心能力:
    - 项目管理（创建/配置/删除）
    - 文件操作（读/写/列/删/移动，沙箱约束）
    - 命令执行（沙箱内安全执行）
    - 代码搜索（正则/文本）
    - Git 快照（自动 commit + 审阅 + 回滚）
    """

    name = "aegis_workspace"
    display_name = "AegisCode 工作区"
    description = "AegisCode 工作区管理——项目、文件、沙箱执行、Git 快照、工具执行器"
    version = "0.1.0"
    author = "AegisCode"
    dependencies: tuple[str, ...] = ("aegis_agent",)

    def on_load(self) -> None:
        logger.info("[AegisWorkspace] loaded into memory")

    async def install(self) -> None:
        """创建表 + seed 菜单。"""
        from src.db import engine
        from src.models.mixins import IDMixin, TimestampMixin  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(
                    sync_conn,
                    tables=[
                        WorkspaceProject.__table__,
                        WorkspaceFile.__table__,
                        WorkspaceSnapshot.__table__,
                        WorkspaceExecution.__table__,
                        WorkspaceProjectMember.__table__,
                    ],
                )
            )

        async with SessionLocal() as db:
            await seed_aegis_workspace_data(db)
            await db.commit()
        logger.info("[AegisWorkspace] installed — tables ready, menus seeded")

    async def uninstall(self) -> None:
        """删除表 + 清理菜单。"""
        async with SessionLocal() as db:
            from src.db import engine
            async with engine.begin() as conn:
                await conn.run_sync(
                    lambda sync_conn: Base.metadata.drop_all(
                        sync_conn,
                        tables=[
                            WorkspaceProjectMember.__table__,
                            WorkspaceExecution.__table__,
                            WorkspaceSnapshot.__table__,
                            WorkspaceFile.__table__,
                            WorkspaceProject.__table__,
                        ],
                    )
                )

            from src.models import Menu
            await db.execute(
                delete(Menu).where(Menu.permission.like("aegis_workspace:%"))
            )
            await db.commit()
        logger.info("[AegisWorkspace] uninstalled — tables dropped, menus removed")

    def register(self, app: FastAPI) -> None:
        """注册路由。"""
        from src.plugins.builtin.aegis_workspace.api import router
        from src.plugins.builtin.aegis_workspace.member_api import router as member_router

        app.include_router(router, prefix=settings.API_PREFIX)
        app.include_router(member_router, prefix=settings.API_PREFIX)
        logger.info("[AegisWorkspace] registered — routes (incl. members)")

    def register_mcp_tools(self) -> None:
        """注册 MCP 工具。"""
        from src.plugins.builtin.aegis_workspace.mcp_tools import register_aegis_workspace_mcp_tools

        register_aegis_workspace_mcp_tools()

    def unregister(self, app: FastAPI) -> None:
        logger.info("[AegisWorkspace] unregistered")

    def on_unload(self) -> None:
        logger.info("[AegisWorkspace] unloaded from memory")
