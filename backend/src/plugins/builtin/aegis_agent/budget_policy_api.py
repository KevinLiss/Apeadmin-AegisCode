"""Agent 预算策略管理 API。

路由前缀: /aegis-budget
权限标识: aegis_budget:*

接口:
- GET    /policies           策略列表
- POST   /policies           创建策略
- PUT    /policies/{id}      更新策略
- DELETE /policies/{id}      删除策略
- GET    /policies/match     查询匹配策略（预览）
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import require_permission
from src.core.exceptions import ConflictException, NotFoundException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.aegis_agent.budget_policy_models import AgentBudgetPolicy

router = APIRouter(prefix="/aegis-budget", tags=["Agent 预算策略"])


def _policy_to_dict(p: AgentBudgetPolicy) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "model_name": p.model_name,
        "user_id": p.user_id,
        "task_type": p.task_type,
        "segment_rounds": p.segment_rounds,
        "max_rounds": p.max_rounds,
        "max_tool_calls": p.max_tool_calls,
        "max_seconds": p.max_seconds,
        "max_tokens": p.max_tokens,
        "max_consecutive_failures": p.max_consecutive_failures,
        "max_cost_usd": p.max_cost_usd,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/policies")
async def list_policies(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_budget:list"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None, description="按启用状态筛选"),
):
    """列出预算策略（分页）。"""
    stmt = select(AgentBudgetPolicy).order_by(AgentBudgetPolicy.id)
    if is_active is not None:
        stmt = stmt.where(AgentBudgetPolicy.is_active == is_active)

    # 计算总数
    from sqlalchemy import func as sql_func
    count_stmt = select(sql_func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()

    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_policy_to_dict(p) for p in items],
    })


@router.post("/policies")
async def create_policy(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_budget:add"))],
):
    """创建预算策略。"""
    # 检查名称唯一
    exists = (
        await db.execute(
            select(AgentBudgetPolicy).where(AgentBudgetPolicy.name == body["name"])
        )
    ).scalar_one_or_none()
    if exists:
        raise ConflictException(f"策略 '{body['name']}' 已存在")

    policy = AgentBudgetPolicy(
        name=body["name"],
        model_name=body.get("model_name"),
        user_id=body.get("user_id"),
        task_type=body.get("task_type"),
        segment_rounds=body.get("segment_rounds", 25),
        max_rounds=body.get("max_rounds", 75),
        max_tool_calls=body.get("max_tool_calls", 150),
        max_seconds=body.get("max_seconds", 3600),
        max_tokens=body.get("max_tokens", 500000),
        max_consecutive_failures=body.get("max_consecutive_failures", 5),
        max_cost_usd=body.get("max_cost_usd", 0.0),
        is_active=body.get("is_active", True),
    )
    db.add(policy)
    await db.commit()
    return success_response(data={"id": policy.id}, msg="创建成功")


@router.put("/policies/{policy_id}")
async def update_policy(
    policy_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_budget:edit"))],
):
    """更新预算策略。"""
    policy = await db.get(AgentBudgetPolicy, policy_id)
    if not policy:
        raise NotFoundException("策略不存在")

    if "name" in body:
        # 检查名称唯一
        if body["name"] != policy.name:
            exists = (
                await db.execute(
                    select(AgentBudgetPolicy).where(
                        AgentBudgetPolicy.name == body["name"]
                    )
                )
            ).scalar_one_or_none()
            if exists:
                raise ConflictException(f"策略 '{body['name']}' 已存在")
        policy.name = body["name"]

    for field in [
        "model_name", "user_id", "task_type",
        "segment_rounds", "max_rounds", "max_tool_calls",
        "max_seconds", "max_tokens", "max_consecutive_failures",
        "max_cost_usd", "is_active",
    ]:
        if field in body:
            setattr(policy, field, body[field])

    await db.commit()
    return success_response(msg="更新成功")


@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_budget:delete"))],
):
    """删除预算策略。"""
    policy = await db.get(AgentBudgetPolicy, policy_id)
    if not policy:
        raise NotFoundException("策略不存在")
    await db.delete(policy)
    await db.commit()
    return success_response(msg="删除成功")


@router.get("/policies/match")
async def match_policy(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_budget:list"))],
    model_name: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    task_type: Optional[str] = Query(None),
):
    """查询匹配的预算策略（按精确度从高到低匹配）。

    匹配优先级:
    1. model + user + task_type
    2. model + user
    3. model + task_type
    4. model only
    5. user + task_type
    6. user only
    7. task_type only
    8. global (all null)
    """
    all_policies = (
        await db.execute(
            select(AgentBudgetPolicy).where(AgentBudgetPolicy.is_active == True)
        )
    ).scalars().all()

    if not all_policies:
        return success_response(data=None, msg="无匹配策略")

    def match_score(p: AgentBudgetPolicy) -> int:
        score = 0
        if p.model_name is not None:
            if p.model_name == model_name:
                score += 100
            else:
                return -1  # 不匹配
        if p.user_id is not None:
            if p.user_id == user_id:
                score += 10
            else:
                return -1
        if p.task_type is not None:
            if p.task_type == task_type:
                score += 1
            else:
                return -1
        return score

    best = None
    best_score = -1
    for p in all_policies:
        score = match_score(p)
        if score > best_score:
            best_score = score
            best = p

    if best and best_score >= 0:
        return success_response(data=_policy_to_dict(best), msg="匹配成功")
    return success_response(data=None, msg="无匹配策略")
