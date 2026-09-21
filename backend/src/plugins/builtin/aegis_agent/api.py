"""AegisCode Agent API 路由。

路由前缀: /aegis-agent
权限标识: aegis_agent:*

接口:
- POST   /runs            创建运行
- GET    /runs            列表
- GET    /runs/{id}       详情
- DELETE /runs/{id}       删除
- POST   /runs/{id}/message  发送消息
- POST   /runs/{id}/control  控制运行
- GET    /runs/{id}/status   实时状态
- POST   /runs/{id}/checkpoint  保存检查点
- POST   /runs/{id}/restore    从检查点恢复
- GET    /runs/{id}/steps      步骤列表
- GET    /runs/{id}/usage      用量日志
- GET    /usage/summary        用量汇总
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user, require_permission
from src.core.exceptions import (
    NotFoundException,
    ValidationException,
    success_response,
)
from src.db import get_db
from src.models import User
from src.plugins.builtin.aegis_agent.models import (
    AgentCheckpoint,
    AgentEvent,
    AgentRun,
    AgentStep,
    AgentUsageLog,
)
from src.plugins.builtin.aegis_agent.runtime import agent_runtime, RunState
from src.plugins.builtin.aegis_agent.schemas import (
    BudgetStatus,
    RunArchive,
    RunControl,
    RunCreate,
    RunMessage,
    RunOut,
    RunPin,
    RunRename,
    StepOut,
    UsageLogOut,
    UsageSummary,
)

router = APIRouter(prefix="/aegis-agent", tags=["AegisCode Agent"])


# ---------------------------------------------------------------------------
# 运行 CRUD
# ---------------------------------------------------------------------------

@router.post("/runs")
async def create_run(
    body: RunCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:create"))],
):
    """创建 Agent 运行。"""
    run = await agent_runtime.create_run(
        user_id=user.id,
        workspace_id=body.workspace_id,
        provider_id=body.provider_id,
        model_name=body.model_name,
        title=body.title,
        max_tokens=body.max_tokens,
        max_steps=body.max_steps,
        max_cost_usd=body.max_cost_usd,
        workflow_type=body.workflow_type.value,
        system_prompt=body.system_prompt,
    )
    return success_response(data={"id": run.id, "status": run.status}, msg="运行已创建")


@router.get("/runs")
async def list_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:list"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    workspace_id: int | None = Query(default=None, description="按项目过滤会话"),
    include_archived: bool = Query(default=False, description="是否包含已归档会话"),
):
    """分页查询运行列表（工作台传 workspace_id 拉取项目下的会话）。

    - 默认排除归档会话，传 include_archived=true 时返回全部
    - 置顶会话排在最前，其余按 id 倒序
    """
    stmt = select(AgentRun).order_by(
        AgentRun.is_pinned.desc(), AgentRun.id.desc()
    )
    if status:
        stmt = stmt.where(AgentRun.status == status)
    if workspace_id is not None:
        stmt = stmt.where(AgentRun.workspace_id == workspace_id)
    if not include_archived:
        stmt = stmt.where(AgentRun.is_archived == False)

    count_stmt = select(func.count()).select_from(AgentRun)
    if status:
        count_stmt = count_stmt.where(AgentRun.status == status)
    if workspace_id is not None:
        count_stmt = count_stmt.where(AgentRun.workspace_id == workspace_id)
    if not include_archived:
        count_stmt = count_stmt.where(AgentRun.is_archived == False)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()

    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [RunOut.model_validate(item) for item in items],
    })


@router.get("/runs/{run_id}")
async def get_run(
    run_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:detail"))],
):
    """获取运行详情。"""
    run = await db.get(AgentRun, run_id)
    if not run:
        raise NotFoundException("运行不存在")
    return success_response(data=RunOut.model_validate(run).model_dump())


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:delete"))],
):
    """删除运行（含步骤、用量、事件、检查点）。"""
    run = await db.get(AgentRun, run_id)
    if not run:
        raise NotFoundException("运行不存在")

    # 清理关联数据
    await db.execute(delete(AgentStep).where(AgentStep.run_id == run_id))
    await db.execute(delete(AgentUsageLog).where(AgentUsageLog.run_id == run_id))
    await db.execute(delete(AgentEvent).where(AgentEvent.run_id == run_id))
    await db.execute(delete(AgentCheckpoint).where(AgentCheckpoint.run_id == run_id))
    await db.delete(run)
    await db.commit()

    # 清理内存
    agent_runtime._active_runs.pop(run_id, None)

    return success_response(msg="删除成功")


@router.put("/runs/{run_id}/title")
async def rename_run(
    run_id: int,
    body: RunRename,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:control"))],
):
    """重命名会话标题。"""
    run = await db.get(AgentRun, run_id)
    if not run:
        raise NotFoundException("运行不存在")

    run.title = body.title.strip()
    await db.commit()
    return success_response(msg="已重命名")


@router.put("/runs/{run_id}/pin")
async def toggle_pin(
    run_id: int,
    body: RunPin,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:control"))],
):
    """置顶/取消置顶。"""
    run = await db.get(AgentRun, run_id)
    if not run:
        raise NotFoundException("运行不存在")

    run.is_pinned = body.is_pinned
    await db.commit()
    return success_response(msg="已置顶" if body.is_pinned else "已取消置顶")


@router.put("/runs/{run_id}/archive")
async def toggle_archive(
    run_id: int,
    body: RunArchive,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:control"))],
):
    """归档/取消归档。"""
    run = await db.get(AgentRun, run_id)
    if not run:
        raise NotFoundException("运行不存在")

    run.is_archived = body.is_archived
    await db.commit()
    return success_response(msg="已归档" if body.is_archived else "已取消归档")


# ---------------------------------------------------------------------------
# 运行交互
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/message")
async def send_message(
    run_id: int,
    body: RunMessage,
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:control"))],
):
    """向 Agent 发送消息。

    stream=true 时返回 SSE 事件流。
    """
    try:
        if body.stream:
            generator = await agent_runtime.send_message(run_id, body.content, stream=True)

            async def _stream():
                async for event in generator:
                    yield f"data: {event}\n\n"

            return StreamingResponse(_stream(), media_type="text/event-stream")
        else:
            result = await agent_runtime.send_message(run_id, body.content, stream=False)
            return success_response(data=result)
    except ValueError as exc:
        # "Run X not found or not active" 等状态错误 → 404/400，而非未处理 500
        if "not found" in str(exc):
            raise NotFoundException(str(exc))
        raise ValidationException(str(exc))


@router.post("/runs/{run_id}/subscribe")
async def subscribe_run(
    run_id: int,
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:control"))],
):
    """重新订阅运行中的 run（切回会话时续接 SSE 事件流）。"""
    try:
        generator = await agent_runtime.subscribe_run(run_id)

        async def _stream():
            async for event in generator:
                yield f"data: {event}\n\n"

        return StreamingResponse(_stream(), media_type="text/event-stream")
    except ValueError as exc:
        if "not found" in str(exc):
            raise NotFoundException(str(exc))
        raise ValidationException(str(exc))


@router.post("/runs/{run_id}/control")
async def control_run(
    run_id: int,
    body: RunControl,
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:control"))],
):
    """控制运行: pause / resume / cancel。"""
    try:
        result = await agent_runtime.control(run_id, body.action)
    except ValueError as exc:
        if "not found" in str(exc):
            raise NotFoundException(str(exc))
        raise ValidationException(str(exc))
    return success_response(data=result)


@router.post("/runs/{run_id}/approve")
async def approve_command(
    run_id: int,
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:control"))],
    decision: bool = Query(..., description="true=批准 false=拒绝"),
):
    """批准/拒绝运行中待审批的高危命令。"""
    active = agent_runtime._active_runs.get(run_id)
    if not active or not active.pending_approval:
        raise NotFoundException("当前没有待审批的命令")
    active.approval_decision = decision
    active.approval_event.set()
    cmd = active.pending_approval.get("command", "")
    return success_response(
        msg="已批准命令执行" if decision else "已拒绝命令执行",
        data={"command": cmd, "approved": decision},
    )


@router.get("/runs/{run_id}/status")
async def get_run_status(
    run_id: int,
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:detail"))],
):
    """获取实时运行状态（含预算信息）。"""
    try:
        status = await agent_runtime.get_status(run_id)
    except ValueError as exc:
        raise NotFoundException(str(exc))
    return success_response(data=status)


# ---------------------------------------------------------------------------
# 检查点
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/checkpoint")
async def create_checkpoint(
    run_id: int,
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:control"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """保存检查点。"""
    checkpoint = await agent_runtime.save_checkpoint(run_id)
    if not checkpoint:
        raise NotFoundException("运行未活跃或不存在")
    return success_response(data={"id": checkpoint.id, "step_index": checkpoint.step_index}, msg="检查点已保存")


@router.post("/runs/{run_id}/restore")
async def restore_run(
    run_id: int,
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:control"))],
):
    """从检查点恢复运行。"""
    success = await agent_runtime.restore_from_checkpoint(run_id)
    if not success:
        raise NotFoundException("没有可用的检查点")
    return success_response(msg="已从检查点恢复")


@router.get("/runs/{run_id}/checkpoints")
async def list_checkpoints(
    run_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:detail"))],
):
    """列出运行的所有检查点。"""
    stmt = (
        select(AgentCheckpoint)
        .where(AgentCheckpoint.run_id == run_id)
        .order_by(AgentCheckpoint.id.desc())
    )
    items = (await db.execute(stmt)).scalars().all()
    return success_response(data=[
        {
            "id": c.id,
            "step_index": c.step_index,
            "is_active": c.is_active,
            "reason": c.reason,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in items
    ])


# ---------------------------------------------------------------------------
# 步骤与用量
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/steps")
async def list_steps(
    run_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:detail"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    """列出运行的步骤。"""
    stmt = (
        select(AgentStep)
        .where(AgentStep.run_id == run_id)
        .order_by(AgentStep.step_index.asc(), AgentStep.id.asc())
    )
    items = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return success_response(data=[StepOut.model_validate(item) for item in items])


@router.get("/runs/{run_id}/messages")
async def list_messages(
    run_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:detail"))],
):
    """将会话步骤还原为聊天消息序列（供工作台对话区渲染历史）。

    每条消息: {role, content, tool_calls?, tool_result?, step_index, created_at}
    - user 消息从 input_messages 中提取
    - assistant 消息取 output_content + tool_calls_json
    - tool 消息取 tool_name + tool_result
    """
    run = await db.get(AgentRun, run_id)
    if not run:
        raise NotFoundException("运行不存在")

    stmt = (
        select(AgentStep)
        .where(AgentStep.run_id == run_id)
        .order_by(AgentStep.step_index.asc(), AgentStep.id.asc())
    )
    steps = (await db.execute(stmt)).scalars().all()

    messages: list[dict] = []
    for s in steps:
        # 用户消息（从 input_messages 中提取最后一条 user 消息）。
        # 注意: input_messages 是完整 LLM 输入（含全部历史），
        # 只有最后一条 user 是本步骤的新输入，取全部会导致跨轮重复。
        if s.step_type == "llm_call" and s.input_messages:
            try:
                input_list = json.loads(s.input_messages) if isinstance(s.input_messages, str) else s.input_messages
                user_msgs = [
                    m for m in (input_list or [])
                    if isinstance(m, dict) and m.get("role") == "user"
                ]
                if user_msgs:
                    messages.append({
                        "role": "user",
                        "content": user_msgs[-1].get("content", ""),
                        "step_index": s.step_index,
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                    })
            except (json.JSONDecodeError, TypeError):
                pass

        # Assistant 输出
        if s.step_type == "llm_call" and s.output_content:
            tool_calls = None
            if s.tool_calls_json:
                try:
                    tool_calls = json.loads(s.tool_calls_json) if isinstance(s.tool_calls_json, str) else s.tool_calls_json
                except (json.JSONDecodeError, TypeError):
                    pass
            messages.append({
                "role": "assistant",
                "content": s.output_content,
                "reasoning_content": s.reasoning_content,
                "tool_calls": tool_calls,
                "role_label": s.role,
                "step_index": s.step_index,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })

        # 工具执行结果
        if s.step_type == "tool_result" and s.tool_name:
            result = None
            if s.tool_result:
                try:
                    result = json.loads(s.tool_result) if isinstance(s.tool_result, str) else s.tool_result
                except (json.JSONDecodeError, TypeError):
                    result = s.tool_result
            messages.append({
                "role": "tool",
                "tool_name": s.tool_name,
                "tool_args": json.loads(s.tool_args) if s.tool_args else None,
                "tool_result": result,
                "tool_success": s.tool_success,
                "step_index": s.step_index,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })

    return success_response(data={"run_id": run_id, "status": run.status, "messages": messages})


@router.get("/runs/{run_id}/usage")
async def list_usage_logs(
    run_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:runs:detail"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    """列出运行的用量日志。"""
    stmt = (
        select(AgentUsageLog)
        .where(AgentUsageLog.run_id == run_id)
        .order_by(AgentUsageLog.id.asc())
    )
    items = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return success_response(data=[UsageLogOut.model_validate(item) for item in items])


# ---------------------------------------------------------------------------
# 用量汇总
# ---------------------------------------------------------------------------

@router.get("/usage/summary")
async def get_usage_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:usage:list"))],
    run_id: int | None = Query(default=None),
    model: str | None = Query(default=None),
):
    """用量汇总（按多维度聚合）。"""
    stmt = select(AgentUsageLog)
    if run_id:
        stmt = stmt.where(AgentUsageLog.run_id == run_id)
    if model:
        stmt = stmt.where(AgentUsageLog.model == model)

    logs = (await db.execute(stmt)).scalars().all()

    if not logs:
        return success_response(data=UsageSummary().model_dump())

    summary = UsageSummary(
        total_input_tokens=sum(l.input_tokens for l in logs),
        total_output_tokens=sum(l.output_tokens for l in logs),
        total_cache_read=sum(l.cache_read_tokens for l in logs),
        total_cache_write=sum(l.cache_write_tokens for l in logs),
        total_reasoning_tokens=sum(l.reasoning_tokens for l in logs),
        total_cost_usd=sum(l.cost_usd for l in logs),
        call_count=len(logs),
        avg_latency_ms=round(sum(l.latency_ms or 0 for l in logs) / len(logs), 1),
    )
    return success_response(data=summary.model_dump())
