"""AegisCode 安全中心 API 路由。

路由前缀: /aegis-security
权限标识: aegis_security:*

接口:
- GET  /token-stats         Token 用量统计（总览/按用户/按模型）
- GET  /call-logs            API 调用日志列表
- GET  /project-token-trend  项目 Token 用量趋势
- GET  /action-logs          用户操作日志列表
- GET  /sanitize-rules       脱敏规则列表
- POST /sanitize-rules       创建脱敏规则
- PUT  /sanitize-rules/{id}  更新脱敏规则
- DELETE /sanitize-rules/{id} 删除脱敏规则
- GET  /users/{user_id}/daily-usage  用户当日 Token 用量
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import require_permission
from src.core.exceptions import NotFoundException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.aegis_agent.security_models import (
    ApiCallLog,
    SanitizeRule,
    UserActionLog,
)

router = APIRouter(prefix="/aegis-security", tags=["AegisCode 安全中心"])


# ---------------------------------------------------------------------------
# Token 统计
# ---------------------------------------------------------------------------

@router.get("/token-stats")
async def token_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_security:token-stats"))],
    days: int = Query(default=7, ge=1, le=90, description="统计最近N天"),
):
    """Token 用量统计总览。"""
    since = datetime.now() - timedelta(days=days)

    # 总量
    stmt = select(
        func.sum(ApiCallLog.input_tokens).label("total_input"),
        func.sum(ApiCallLog.output_tokens).label("total_output"),
        func.sum(ApiCallLog.total_tokens).label("total_tokens"),
        func.sum(ApiCallLog.cost_usd).label("total_cost"),
        func.count(ApiCallLog.id).label("call_count"),
    ).where(ApiCallLog.created_at >= since)
    row = (await db.execute(stmt)).one()

    # 按用户 Top 10
    user_stmt = (
        select(
            ApiCallLog.user_id,
            User.username,
            User.nickname,
            func.sum(ApiCallLog.total_tokens).label("tokens"),
            func.sum(ApiCallLog.cost_usd).label("cost"),
            func.count(ApiCallLog.id).label("calls"),
        )
        .join(User, ApiCallLog.user_id == User.id)
        .where(ApiCallLog.created_at >= since)
        .group_by(ApiCallLog.user_id, User.username, User.nickname)
        .order_by(func.sum(ApiCallLog.total_tokens).desc())
        .limit(10)
    )
    top_users = (await db.execute(user_stmt)).all()

    # 按模型
    model_stmt = (
        select(
            ApiCallLog.model,
            func.sum(ApiCallLog.total_tokens).label("tokens"),
            func.sum(ApiCallLog.cost_usd).label("cost"),
            func.count(ApiCallLog.id).label("calls"),
        )
        .where(ApiCallLog.created_at >= since)
        .group_by(ApiCallLog.model)
        .order_by(func.sum(ApiCallLog.total_tokens).desc())
    )
    by_model = (await db.execute(model_stmt)).all()

    # 按日期趋势
    daily_stmt = (
        select(
            func.date(ApiCallLog.created_at).label("date"),
            func.sum(ApiCallLog.total_tokens).label("tokens"),
            func.sum(ApiCallLog.cost_usd).label("cost"),
            func.count(ApiCallLog.id).label("calls"),
        )
        .where(ApiCallLog.created_at >= since)
        .group_by(func.date(ApiCallLog.created_at))
        .order_by(func.date(ApiCallLog.created_at))
    )
    daily = (await db.execute(daily_stmt)).all()

    return success_response(data={
        "summary": {
            "total_input": row.total_input or 0,
            "total_output": row.total_output or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost": float(row.total_cost or 0),
            "call_count": row.call_count or 0,
            "days": days,
        },
        "top_users": [
            {
                "user_id": r.user_id,
                "username": r.username,
                "nickname": r.nickname,
                "tokens": r.tokens or 0,
                "cost": float(r.cost or 0),
                "calls": r.calls or 0,
            }
            for r in top_users
        ],
        "by_model": [
            {
                "model": r.model,
                "tokens": r.tokens or 0,
                "cost": float(r.cost or 0),
                "calls": r.calls or 0,
            }
            for r in by_model
        ],
        "daily_trend": [
            {
                "date": str(r.date),
                "tokens": r.tokens or 0,
                "cost": float(r.cost or 0),
                "calls": r.calls or 0,
            }
            for r in daily
        ],
    })


@router.get("/call-logs")
async def list_call_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_security:call-logs"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int | None = Query(default=None),
    model: str | None = Query(default=None),
    start_date: str | None = Query(default=None, description="YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="YYYY-MM-DD"),
):
    """API 调用日志列表。"""
    stmt = select(ApiCallLog).order_by(ApiCallLog.id.desc())
    count_stmt = select(func.count()).select_from(ApiCallLog)

    if user_id:
        stmt = stmt.where(ApiCallLog.user_id == user_id)
        count_stmt = count_stmt.where(ApiCallLog.user_id == user_id)
    if model:
        stmt = stmt.where(ApiCallLog.model == model)
        count_stmt = count_stmt.where(ApiCallLog.model == model)
    if start_date:
        stmt = stmt.where(ApiCallLog.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
        count_stmt = count_stmt.where(ApiCallLog.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        stmt = stmt.where(ApiCallLog.created_at < end)
        count_stmt = count_stmt.where(ApiCallLog.created_at < end)

    total = (await db.execute(count_stmt)).scalar() or 0
    items = (
        await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "run_id": l.run_id,
                "model": l.model,
                "provider": l.provider,
                "input_tokens": l.input_tokens,
                "output_tokens": l.output_tokens,
                "total_tokens": l.total_tokens,
                "cost_usd": l.cost_usd,
                "latency_ms": l.latency_ms,
                "workspace_id": l.workspace_id,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in items
        ],
    })


@router.get("/users/{user_id}/daily-usage")
async def user_daily_usage(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_security:token-stats"))],
):
    """用户当日 Token 用量。"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    stmt = (
        select(
            func.sum(ApiCallLog.total_tokens).label("used"),
            func.count(ApiCallLog.id).label("calls"),
            func.sum(ApiCallLog.cost_usd).label("cost"),
        )
        .where(ApiCallLog.user_id == user_id)
        .where(ApiCallLog.created_at >= today_start)
    )
    row = (await db.execute(stmt)).one()

    # 获取用户限额
    target = await db.get(User, user_id)
    limit = target.token_limit if target else 0

    used = row.used or 0
    return success_response(data={
        "user_id": user_id,
        "token_limit": limit,
        "used_today": used,
        "remaining": max(0, limit - used) if limit > 0 else None,
        "calls_today": row.calls or 0,
        "cost_today": float(row.cost or 0),
    })


# ---------------------------------------------------------------------------
# 操作日志
# ---------------------------------------------------------------------------

@router.get("/action-logs")
async def list_action_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_security:action-logs"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
):
    """用户操作日志列表。"""
    stmt = select(UserActionLog).order_by(UserActionLog.id.desc())
    count_stmt = select(func.count()).select_from(UserActionLog)

    if user_id:
        stmt = stmt.where(UserActionLog.user_id == user_id)
        count_stmt = count_stmt.where(UserActionLog.user_id == user_id)
    if action:
        stmt = stmt.where(UserActionLog.action == action)
        count_stmt = count_stmt.where(UserActionLog.action == action)

    total = (await db.execute(count_stmt)).scalar() or 0
    items = (
        await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "username": l.username,
                "action": l.action,
                "target_type": l.target_type,
                "target_id": l.target_id,
                "target_name": l.target_name,
                "detail": l.detail,
                "ip_address": l.ip_address,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in items
        ],
    })


# ---------------------------------------------------------------------------
# 脱敏规则
# ---------------------------------------------------------------------------

@router.get("/sanitize-rules")
async def list_sanitize_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_security:sanitize-rules"))],
):
    """脱敏规则列表。"""
    stmt = select(SanitizeRule).order_by(SanitizeRule.priority.desc(), SanitizeRule.id)
    items = (await db.execute(stmt)).scalars().all()
    return success_response(data=[
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "pattern": r.pattern,
            "replacement": r.replacement,
            "enabled": r.enabled,
            "priority": r.priority,
            "category": r.category,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in items
    ])


@router.post("/sanitize-rules")
async def create_sanitize_rule(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_security:sanitize-rules"))],
):
    """创建脱敏规则。"""
    rule = SanitizeRule(
        name=body.get("name", ""),
        description=body.get("description"),
        pattern=body.get("pattern", ""),
        replacement=body.get("replacement", "***"),
        enabled=body.get("enabled", True),
        priority=body.get("priority", 0),
        category=body.get("category"),
    )
    db.add(rule)
    await db.commit()
    return success_response(data={"id": rule.id}, msg="规则已创建")


@router.put("/sanitize-rules/{rule_id}")
async def update_sanitize_rule(
    rule_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_security:sanitize-rules"))],
):
    """更新脱敏规则。"""
    rule = await db.get(SanitizeRule, rule_id)
    if not rule:
        raise NotFoundException("规则不存在")
    for key in ("name", "description", "pattern", "replacement", "enabled", "priority", "category"):
        if key in body:
            setattr(rule, key, body[key])
    await db.commit()
    return success_response(msg="规则已更新")


@router.delete("/sanitize-rules/{rule_id}")
async def delete_sanitize_rule(
    rule_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_security:sanitize-rules"))],
):
    """删除脱敏规则。"""
    rule = await db.get(SanitizeRule, rule_id)
    if not rule:
        raise NotFoundException("规则不存在")
    await db.delete(rule)
    await db.commit()
    return success_response(msg="规则已删除")
