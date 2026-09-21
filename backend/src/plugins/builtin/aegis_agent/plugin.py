"""AegisCode Agent 插件入口类（含工作区子模块）。"""

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
from src.plugins.builtin.aegis_agent.security_models import (  # noqa: F401
    ApiCallLog,
    UserActionLog,
    SanitizeRule,
)
from src.plugins.builtin.aegis_agent.budget_policy_models import (  # noqa: F401
    AgentBudgetPolicy,
)
from src.plugins.builtin.aegis_agent.skill_models import (  # noqa: F401
    Skill,
    ToolConfig,
)
from src.plugins.builtin.aegis_agent.mcp_server_models import (  # noqa: F401
    McpServer,
)
from src.plugins.builtin.aegis_agent.workspace.models import (  # noqa: F401
    WorkspaceExecution,
    WorkspaceFile,
    WorkspaceProject,
    WorkspaceSnapshot,
)
from src.plugins.builtin.aegis_agent.workspace.member_models import (  # noqa: F401
    WorkspaceProjectMember,
)
from src.plugins.builtin.aegis_agent.seed import seed_aegis_agent_data
from src.plugins.builtin.aegis_agent.workspace.seed import seed_aegis_workspace_data


class AegisAgentPlugin(PluginInterface):
    """AegisCode 核心插件：Agent 运行时 + 工作区管理。

    Agent 运行时:
    - 状态机驱动的对话循环
    - 精确 Token 计量（API usage 返回值，非粗估）
    - 分层上下文管理（压缩是视图不是删除）
    - 三重循环检测、检查点/暂停/恢复
    - 预算策略 / 技能中心 / MCP 服务器 / 安全中心

    工作区:
    - 项目管理（创建/配置/删除、成员协作）
    - 文件操作（读/写/列/删/移动，沙箱约束）
    - 命令执行（沙箱内安全执行）
    - 代码搜索（正则/文本）
    - Git 快照（自动 commit + 审阅 + 回滚）
    """

    name = "aegis_agent"
    display_name = "AegisCode"
    description = "AegisCode 一体化插件——Agent 运行时（状态机对话循环、精确 Token 计量、分层上下文管理、预算/技能/MCP/安全）+ 工作区（项目、文件、沙箱执行、Git 快照、成员协作）"
    version = "0.2.0"
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
                        ApiCallLog.__table__,
                        UserActionLog.__table__,
                        SanitizeRule.__table__,
                        AgentBudgetPolicy.__table__,
                        Skill.__table__,
                        ToolConfig.__table__,
                        McpServer.__table__,
                        # 工作区
                        WorkspaceProject.__table__,
                        WorkspaceFile.__table__,
                        WorkspaceSnapshot.__table__,
                        WorkspaceExecution.__table__,
                        WorkspaceProjectMember.__table__,
                    ],
                )
            )

        async with SessionLocal() as db:
            await seed_aegis_agent_data(db)
            await seed_aegis_workspace_data(db)
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
                            # 工作区
                            WorkspaceProjectMember.__table__,
                            WorkspaceExecution.__table__,
                            WorkspaceSnapshot.__table__,
                            WorkspaceFile.__table__,
                            WorkspaceProject.__table__,
                            # Agent
                            SanitizeRule.__table__,
                            UserActionLog.__table__,
                            ApiCallLog.__table__,
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
                delete(Menu).where(
                    (Menu.permission.like("aegis_agent:%"))
                    | (Menu.permission.like("aegis_workspace:%"))
                    | (Menu.permission.like("aegis_security:%"))
                    | (Menu.permission.like("aegis_budget:%"))
                    | (Menu.permission.like("aegis_skill:%"))
                    | (Menu.permission.like("aegis_mcp:%"))
                )
            )
            await db.execute(
                delete(Menu).where(Menu.path == "/aegis-agent")
            )
            await db.commit()
        logger.info("[AegisAgent] uninstalled — tables dropped, menus removed")

    def register(self, app: FastAPI) -> None:
        """注册路由。"""
        from src.plugins.builtin.aegis_agent.api import router
        from src.plugins.builtin.aegis_agent.security_api import router as security_router
        from src.plugins.builtin.aegis_agent.budget_policy_api import router as budget_router
        from src.plugins.builtin.aegis_agent.skill_api import router as skill_router
        from src.plugins.builtin.aegis_agent.mcp_server_api import router as mcp_router
        from src.plugins.builtin.aegis_agent.workspace.api import router as workspace_router
        from src.plugins.builtin.aegis_agent.workspace.member_api import router as member_router

        app.include_router(router, prefix=settings.API_PREFIX)
        app.include_router(security_router, prefix=settings.API_PREFIX)
        app.include_router(budget_router, prefix=settings.API_PREFIX)
        app.include_router(skill_router, prefix=settings.API_PREFIX)
        app.include_router(mcp_router, prefix=settings.API_PREFIX)
        app.include_router(workspace_router, prefix=settings.API_PREFIX)
        app.include_router(member_router, prefix=settings.API_PREFIX)

        # 订阅事件（示例：日志记录）
        event_bus.on(
            Event.USER_LOGIN,
            self._on_user_login,
            plugin_name=self.name,
        )
        logger.info("[AegisAgent] registered — routes (agent + workspace) + event subscription")

    def register_mcp_tools(self) -> None:
        """注册 MCP 工具。"""
        from src.plugins.builtin.aegis_agent.mcp_tools import register_aegis_agent_mcp_tools
        from src.plugins.builtin.aegis_agent.workspace.mcp_tools import register_aegis_workspace_mcp_tools

        register_aegis_agent_mcp_tools()
        register_aegis_workspace_mcp_tools()

    def unregister(self, app: FastAPI) -> None:
        logger.info("[AegisAgent] unregistered — runtime resources released")

    def on_unload(self) -> None:
        logger.info("[AegisAgent] unloaded from memory")

    async def _on_user_login(self, *args, **kwargs) -> None:
        user_id = kwargs.get("user_id", "unknown")
        logger.debug(f"[AegisAgent] user login: {user_id}")
