"""技能中心 API：Skill CRUD + ToolConfig CRUD + 技能市场。

路由前缀: /aegis-skill
权限标识: aegis_skill:*
"""

import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sql_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import require_permission
from src.core.exceptions import ConflictException, NotFoundException, success_response, ValidationException
from src.db import get_db
from src.models import User
from src.plugins.builtin.aegis_agent.skill_models import Skill, ToolConfig

router = APIRouter(prefix="/aegis-skill", tags=["技能中心"])


def _load_json(text: str | None, default):
    try:
        return json.loads(text) if text else default
    except (json.JSONDecodeError, TypeError):
        return default


def _skill_to_dict(s: Skill) -> dict:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "name": s.name,
        "display_name": s.display_name,
        "description": s.description,
        "category": s.category,
        "skill_type": s.skill_type,
        "icon": s.icon,
        "system_prompt": s.system_prompt,
        "tools": _load_json(s.tools, []),
        "params_schema": _load_json(s.params_schema, []),
        "is_active": s.is_active,
        "in_market": s.in_market,
        "review_status": s.review_status,
        "review_comment": s.review_comment,
        "tool_sources": _load_json(s.tool_sources, []),
        "source_skill_id": s.source_skill_id,
        "sort_order": s.sort_order,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _tool_to_dict(t: ToolConfig) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "display_name": t.display_name,
        "description": t.description,
        "category": t.category,
        "tool_sources": _load_json(t.tool_sources, []),
        "params_schema": _load_json(t.params_schema, []),
        "source": t.source,
        "is_active": t.is_active,
        "is_readonly": t.is_readonly,
        "sort_order": t.sort_order,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


# ---------------------------------------------------------------------------
# Skill CRUD
# ---------------------------------------------------------------------------

@router.get("/skills")
async def list_skills(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:list"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    keyword: Optional[str] = Query(None, description="按名称/显示名模糊搜索"),
):
    """技能列表（分页 + 筛选）。"""
    stmt = select(Skill).order_by(Skill.sort_order, Skill.id)
    if category:
        stmt = stmt.where(Skill.category == category)
    if is_active is not None:
        stmt = stmt.where(Skill.is_active == is_active)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(Skill.name.like(like) | Skill.display_name.like(like))

    count_stmt = select(sql_func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()

    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_skill_to_dict(s) for s in items],
    })


@router.post("/skills")
async def create_skill(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:add"))],
):
    """创建技能。"""
    name = body.get("name", "").strip()
    if not name:
        raise ConflictException("技能名称不能为空")

    # 同名检查（全局唯一：系统内置+各用户隔离）
    exists = (
        await db.execute(
            select(Skill).where(Skill.name == name, Skill.user_id == body.get("user_id"))
        )
    ).scalar_one_or_none()
    if exists:
        raise ConflictException(f"技能 '{name}' 已存在")

    skill = Skill(
        user_id=body.get("user_id"),
        name=name,
        display_name=body.get("display_name") or name,
        description=body.get("description", ""),
        category=body.get("category", "general"),
        skill_type=body.get("skill_type", "builtin"),
        icon=body.get("icon", "⚡"),
        system_prompt=body.get("system_prompt", ""),
        tools=json.dumps(body.get("tools", []), ensure_ascii=False),
        params_schema=json.dumps(body.get("params_schema", []), ensure_ascii=False),
        is_active=body.get("is_active", True),
        in_market=body.get("in_market", False),
        review_status=body.get("review_status", "pending"),
        tool_sources=json.dumps(body.get("tool_sources", []), ensure_ascii=False),
        sort_order=body.get("sort_order", 0),
    )
    db.add(skill)
    await db.commit()
    return success_response(data={"id": skill.id}, msg="创建成功")


@router.put("/skills/{skill_id}")
async def update_skill(
    skill_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:edit"))],
):
    """更新技能。"""
    skill = await db.get(Skill, skill_id)
    if not skill:
        raise NotFoundException("技能不存在")

    if "name" in body and body["name"] != skill.name:
        exists = (
            await db.execute(
                select(Skill).where(
                    Skill.name == body["name"], Skill.user_id == skill.user_id
                )
            )
        ).scalar_one_or_none()
        if exists:
            raise ConflictException(f"技能 '{body['name']}' 已存在")
        skill.name = body["name"]

    simple_fields = [
        "display_name", "description", "category", "skill_type", "icon",
        "system_prompt", "is_active", "in_market", "review_status",
        "review_comment", "sort_order",
    ]
    for field in simple_fields:
        if field in body:
            setattr(skill, field, body[field])

    if "tools" in body:
        skill.tools = json.dumps(body["tools"], ensure_ascii=False)
    if "params_schema" in body:
        skill.params_schema = json.dumps(body["params_schema"], ensure_ascii=False)
    if "tool_sources" in body:
        skill.tool_sources = json.dumps(body["tool_sources"], ensure_ascii=False)

    await db.commit()
    return success_response(msg="更新成功")


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:delete"))],
):
    """删除技能。"""
    skill = await db.get(Skill, skill_id)
    if not skill:
        raise NotFoundException("技能不存在")
    await db.delete(skill)
    await db.commit()
    return success_response(msg="删除成功")


# ---------------------------------------------------------------------------
# ToolConfig CRUD
# ---------------------------------------------------------------------------

@router.get("/tools")
async def list_tools(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:list"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    """工具配置列表（分页）。"""
    stmt = select(ToolConfig).order_by(ToolConfig.sort_order, ToolConfig.id)
    if category:
        stmt = stmt.where(ToolConfig.category == category)
    if source:
        stmt = stmt.where(ToolConfig.source == source)

    count_stmt = select(sql_func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()

    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_tool_to_dict(t) for t in items],
    })


@router.post("/tools")
async def create_tool(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:add"))],
):
    """创建工具配置。"""
    name = body.get("name", "").strip()
    if not name:
        raise ConflictException("工具名称不能为空")

    exists = (
        await db.execute(select(ToolConfig).where(ToolConfig.name == name))
    ).scalar_one_or_none()
    if exists:
        raise ConflictException(f"工具 '{name}' 已存在")

    tool = ToolConfig(
        name=name,
        display_name=body.get("display_name") or name,
        description=body.get("description", ""),
        category=body.get("category", "general"),
        tool_sources=json.dumps(body.get("tool_sources", []), ensure_ascii=False),
        params_schema=json.dumps(body.get("params_schema", []), ensure_ascii=False),
        source=body.get("source", "custom"),
        is_active=body.get("is_active", True),
        is_readonly=False,
        sort_order=body.get("sort_order", 0),
    )
    db.add(tool)
    await db.commit()
    return success_response(data={"id": tool.id}, msg="创建成功")


@router.put("/tools/{tool_id}")
async def update_tool(
    tool_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:edit"))],
):
    """更新工具配置（内置只读工具仅允许修改启停状态）。"""
    tool = await db.get(ToolConfig, tool_id)
    if not tool:
        raise NotFoundException("工具不存在")

    if tool.is_readonly:
        # 只允许启停
        allowed = {"is_active"}
        if not set(body.keys()).issubset(allowed):
            raise ConflictException("内置工具为只读，仅允许修改启用状态")

    if "name" in body and body["name"] != tool.name:
        exists = (
            await db.execute(select(ToolConfig).where(ToolConfig.name == body["name"]))
        ).scalar_one_or_none()
        if exists:
            raise ConflictException(f"工具 '{body['name']}' 已存在")
        tool.name = body["name"]

    simple_fields = ["display_name", "description", "category", "source", "is_active", "sort_order"]
    for field in simple_fields:
        if field in body:
            setattr(tool, field, body[field])

    if "tool_sources" in body:
        tool.tool_sources = json.dumps(body["tool_sources"], ensure_ascii=False)
    if "params_schema" in body:
        tool.params_schema = json.dumps(body["params_schema"], ensure_ascii=False)

    await db.commit()
    return success_response(msg="更新成功")


@router.delete("/tools/{tool_id}")
async def delete_tool(
    tool_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:delete"))],
):
    """删除工具配置（内置只读工具禁止删除）。"""
    tool = await db.get(ToolConfig, tool_id)
    if not tool:
        raise NotFoundException("工具不存在")
    if tool.is_readonly:
        raise ConflictException("内置工具禁止删除")
    await db.delete(tool)
    await db.commit()
    return success_response(msg="删除成功")


# ---------------------------------------------------------------------------
# 技能市场
# ---------------------------------------------------------------------------

@router.get("/market")
async def list_market_skills(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:list"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
):
    """技能市场列表（仅已上架且审核通过的技能）。"""
    stmt = (
        select(Skill)
        .where(Skill.in_market == True, Skill.review_status == "approved")
        .order_by(Skill.sort_order, Skill.id.desc())
    )
    if category:
        stmt = stmt.where(Skill.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(Skill.name.like(like) | Skill.display_name.like(like) | Skill.description.like(like))

    count_stmt = select(sql_func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()

    # 附带安装状态：当前用户是否已安装
    installed_ids = set()
    if items:
        source_ids = [s.id for s in items]
        installed_stmt = select(Skill.source_skill_id).where(
            Skill.source_skill_id.in_(source_ids),
            Skill.user_id == user.id,
        )
        installed_ids = set((await db.execute(installed_stmt)).scalars().all())

    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {**_skill_to_dict(s), "installed": s.id in installed_ids}
            for s in items
        ],
    })


@router.post("/market/{skill_id}/install")
async def install_market_skill(
    skill_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:add"))],
):
    """从市场安装技能到「我的技能」（复制为用户私有副本）。"""
    source = await db.get(Skill, skill_id)
    if not source:
        raise NotFoundException("技能不存在")
    if not source.in_market or source.review_status != "approved":
        raise ValidationException("该技能未上架或未审核通过")

    # 检查是否已安装
    existing = (
        await db.execute(
            select(Skill).where(
                Skill.source_skill_id == skill_id,
                Skill.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictException("已安装该技能")

    # 复制技能为用户私有副本
    clone = Skill(
        user_id=user.id,
        name=f"{source.name}_imported",
        display_name=source.display_name,
        description=source.description,
        category=source.category,
        skill_type="market",
        icon=source.icon,
        system_prompt=source.system_prompt,
        tools=source.tools,
        params_schema=source.params_schema,
        is_active=True,
        in_market=False,
        review_status="approved",  # 市场来源已审核
        tool_sources=source.tool_sources,
        source_skill_id=skill_id,
        sort_order=0,
    )
    db.add(clone)
    await db.commit()
    return success_response(data={"id": clone.id}, msg="技能已安装到我的技能")


@router.post("/skills/{skill_id}/publish")
async def publish_skill_to_market(
    skill_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:edit"))],
):
    """提交技能到市场（设置 in_market=True，进入审核流程）。"""
    skill = await db.get(Skill, skill_id)
    if not skill:
        raise NotFoundException("技能不存在")

    if skill.user_id != user.id and skill.user_id is not None:
        raise ValidationException("只能发布自己的技能")

    if skill.in_market and skill.review_status == "approved":
        raise ConflictException("技能已上架")

    skill.in_market = True
    skill.review_status = "pending"
    await db.commit()
    return success_response(msg="技能已提交到市场，等待审核")


@router.post("/skills/{skill_id}/unpublish")
async def unpublish_skill_from_market(
    skill_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:edit"))],
):
    """从市场下架技能。"""
    skill = await db.get(Skill, skill_id)
    if not skill:
        raise NotFoundException("技能不存在")

    if skill.user_id != user.id and skill.user_id is not None:
        raise ValidationException("只能下架自己的技能")

    skill.in_market = False
    await db.commit()
    return success_response(msg="技能已从市场下架")


@router.get("/my-skills")
async def list_my_skills(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_skill:list"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    skill_type: Optional[str] = Query(None),
):
    """我的技能列表（当前用户创建或安装的技能）。"""
    stmt = (
        select(Skill)
        .where(Skill.user_id == user.id)
        .order_by(Skill.sort_order, Skill.id.desc())
    )
    if skill_type:
        stmt = stmt.where(Skill.skill_type == skill_type)

    count_stmt = select(sql_func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()

    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_skill_to_dict(s) for s in items],
    })
