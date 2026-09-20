"""AegisCode Agent MCP 工具注册。

注册 Agent 管理相关的 MCP 工具，让 AI 助手能查询/管理 Agent 运行。
"""

import json

from loguru import logger
from sqlalchemy import select

from src.db import SessionLocal
from src.mcp import mcp_manager


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

async def _list_agent_runs(status: str | None = None, limit: int = 10) -> str:
    """列出 Agent 运行记录。

    Args:
        status: 筛选状态（created/running/paused/completed/failed/cancelled），留空返回全部
        limit: 返回数量上限，默认 10
    """
    from src.plugins.builtin.aegis_agent.models import AgentRun

    async with SessionLocal() as db:
        stmt = select(AgentRun).order_by(AgentRun.id.desc()).limit(min(limit, 50))
        if status:
            stmt = stmt.where(AgentRun.status == status)
        runs = (await db.execute(stmt)).scalars().all()

    items = [
        {
            "id": r.id,
            "status": r.status,
            "model": r.model_name,
            "steps": r.step_count,
            "input_tokens": r.total_input_tokens,
            "output_tokens": r.total_output_tokens,
            "cost_usd": float(r.total_cost_usd),
        }
        for r in runs
    ]
    return json.dumps({"total": len(items), "items": items}, ensure_ascii=False)


async def _get_agent_run_status(run_id: int) -> str:
    """获取 Agent 运行的实时状态。

    Args:
        run_id: 运行 ID
    """
    from src.plugins.builtin.aegis_agent.runtime import agent_runtime

    status = await agent_runtime.get_status(run_id)
    return json.dumps(status, ensure_ascii=False)


async def _get_usage_summary(run_id: int | None = None) -> str:
    """获取 Agent 用量汇总。

    Args:
        run_id: 指定运行ID，留空汇总全部
    """
    from src.plugins.builtin.aegis_agent.models import AgentUsageLog

    async with SessionLocal() as db:
        stmt = select(AgentUsageLog)
        if run_id:
            stmt = stmt.where(AgentUsageLog.run_id == run_id)
        logs = (await db.execute(stmt)).scalars().all()

    if not logs:
        return json.dumps({"total_calls": 0, "message": "无用量记录"}, ensure_ascii=False)

    summary = {
        "total_calls": len(logs),
        "total_input_tokens": sum(l.input_tokens for l in logs),
        "total_output_tokens": sum(l.output_tokens for l in logs),
        "total_cache_read": sum(l.cache_read_tokens for l in logs),
        "total_cache_write": sum(l.cache_write_tokens for l in logs),
        "total_reasoning_tokens": sum(l.reasoning_tokens for l in logs),
        "total_cost_usd": float(sum(l.cost_usd for l in logs)),
    }
    return json.dumps(summary, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------

def register_aegis_agent_mcp_tools() -> None:
    """注册 AegisCode Agent MCP 工具。"""
    mcp_manager.register_tool(
        name="aegis_list_runs",
        description="列出 AegisCode Agent 运行记录",
        handler=_list_agent_runs,
        plugin_name="aegis_agent",
        category="aegis_agent",
    )
    mcp_manager.register_tool(
        name="aegis_get_run_status",
        description="获取 AegisCode Agent 运行的实时状态和预算信息",
        handler=_get_agent_run_status,
        plugin_name="aegis_agent",
        category="aegis_agent",
    )
    mcp_manager.register_tool(
        name="aegis_get_usage_summary",
        description="获取 AegisCode Agent 用量汇总（Token、成本等）",
        handler=_get_usage_summary,
        plugin_name="aegis_agent",
        category="aegis_agent",
    )
    logger.info("Registered 3 aegis_agent MCP tools")
