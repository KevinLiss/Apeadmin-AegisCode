"""AegisCode 项目成员 API 路由。

挂在 aegis_agent 插件（workspace 子模块）下, 路由前缀复用 /aegis-workspace

接口:
- GET    /projects/{id}/members                成员列表(含 owner)
- POST   /projects/{id}/members                添加成员
- PUT    /projects/{id}/members/{user_id}      修改成员角色/权限
- DELETE /projects/{id}/members/{user_id}      移除成员
- GET    /projects/{id}/members/roles          角色和权限点字典(前端渲染用)
- GET    /projects/{id}/members/candidates     可添加的候选用户列表
"""

import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import require_permission
from src.core.exceptions import (
    NotFoundException,
    ValidationException,
    success_response,
)
from src.db import get_db
from src.models import User
from src.plugins.builtin.aegis_agent.workspace.member_models import (
    AVAILABLE_PERMISSIONS,
    MEMBER_ROLES,
    ROLE_DEFAULT_PERMISSIONS,
    WorkspaceProjectMember,
)
from src.plugins.builtin.aegis_agent.workspace.models import WorkspaceProject

router = APIRouter(prefix="/aegis-workspace", tags=["AegisCode 项目成员"])


def _member_perm(role: str, permissions: str) -> list[str]:
    """返回权限列表, 空则取角色默认权限。"""
    perms = json.loads(permissions) if permissions else []
    if not perms:
        return ROLE_DEFAULT_PERMISSIONS.get(role, [])
    return [str(p) for p in perms]


def _serialize_member(m: WorkspaceProjectMember, u: User) -> dict:
    return {
        "user_id": u.id,
        "username": u.username,
        "nickname": u.nickname or u.username,
        "avatar": u.avatar,
        "email": u.email,
        "role": m.role,
        "permissions": _member_perm(m.role, m.permissions),
        "added_at": m.created_at.isoformat() if m.created_at else None,
    }


async def _get_project_or_404(db: AsyncSession, project_id: int) -> WorkspaceProject:
    project = await db.get(WorkspaceProject, project_id)
    if not project or project.status == "deleted":
        raise NotFoundException("项目不存在")
    return project


# ---------------------------------------------------------------------------
# 字典接口
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/members/roles")
async def get_member_role_dict(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:list"))],
):
    """角色与权限点字典（前端渲染复选框用）。"""
    return success_response(data={
        "roles": [{"value": k, "label": v} for k, v in MEMBER_ROLES.items()],
        "role_defaults": ROLE_DEFAULT_PERMISSIONS,
        "permissions": [{"value": v, "label": l} for v, l in AVAILABLE_PERMISSIONS],
    })


@router.get("/projects/{project_id}/members/candidates")
async def get_member_candidates(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:list"))],
    keyword: Optional[str] = Query(default=None, max_length=50),
    limit: int = Query(default=20, ge=1, le=50),
):
    """可添加为成员的候选用户（排除 owner、已是成员、已禁用的）。"""
    project = await _get_project_or_404(db, project_id)

    existing = select(WorkspaceProjectMember.user_id).where(
        WorkspaceProjectMember.project_id == project_id
    )
    stmt = (
        select(User)
        .where(User.status == 1)
        .where(User.id != project.user_id)
        .where(User.id.not_in(existing))
        .order_by(User.id)
    )
    if keyword:
        stmt = stmt.where(
            (User.username.contains(keyword)) | (User.nickname.contains(keyword))
        )
    users = (await db.execute(stmt.limit(limit))).scalars().all()

    return success_response(data=[
        {"user_id": u.id, "username": u.username, "nickname": u.nickname or u.username, "email": u.email}
        for u in users
    ])


# ---------------------------------------------------------------------------
# 成员 CRUD
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/members")
async def list_project_members(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:list"))],
):
    """项目成员列表（owner 恒在首位）。"""
    project = await _get_project_or_404(db, project_id)

    members = (
        await db.execute(
            select(WorkspaceProjectMember, User)
            .join(User, User.id == WorkspaceProjectMember.user_id)
            .where(WorkspaceProjectMember.project_id == project_id)
            .order_by(WorkspaceProjectMember.id)
        )
    ).all()

    items = []
    # owner
    owner = await db.get(User, project.user_id)
    if owner:
        items.append({
            "user_id": owner.id,
            "username": owner.username,
            "nickname": owner.nickname or owner.username,
            "avatar": owner.avatar,
            "email": owner.email,
            "role": "owner",
            "permissions": ["project:*", "tool:*", "member:manage"],
            "added_at": project.created_at.isoformat() if project.created_at else None,
        })
    for m, u in members:
        items.append(_serialize_member(m, u))

    return success_response(data=items)


@router.post("/projects/{project_id}/members")
async def add_project_member(
    project_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:edit"))],
):
    """添加项目成员。"""
    project = await _get_project_or_404(db, project_id)

    user_id = body.get("user_id")
    role = str(body.get("role") or "member").lower()
    permissions = body.get("permissions") or []

    if not user_id:
        raise ValidationException("请选择用户")
    if role not in MEMBER_ROLES:
        raise ValidationException("项目角色无效")
    if not isinstance(permissions, list) or len(permissions) > 100:
        raise ValidationException("权限必须是数组且不超过100项")
    valid_perms = {v for v, _ in AVAILABLE_PERMISSIONS}
    bad = [p for p in permissions if str(p) not in valid_perms]
    if bad:
        raise ValidationException(f"无效权限点: {bad}")

    if user_id == project.user_id:
        raise ValidationException("创建者已在项目中")

    target = await db.get(User, int(user_id))
    if not target or target.status != 1:
        raise NotFoundException("用户不存在或已禁用")

    existing = (
        await db.execute(
            select(WorkspaceProjectMember).where(
                WorkspaceProjectMember.project_id == project_id,
                WorkspaceProjectMember.user_id == target.id,
            )
        )
    ).scalars().first()
    if existing:
        raise ValidationException(f"用户 '{target.username}' 已是项目成员")

    member = WorkspaceProjectMember(
        project_id=project_id,
        user_id=target.id,
        role=role,
        permissions=json.dumps([str(p) for p in permissions], ensure_ascii=False) if permissions else "[]",
    )
    db.add(member)
    await db.commit()

    # 操作审计
    from src.plugins.builtin.aegis_agent.security_models import UserActionLog
    db.add(UserActionLog(
        user_id=user.id, username=user.username, action="workspace.member.add",
        target_type="project_member", target_id=str(target.id), target_name=target.username,
        detail=json.dumps({"project_id": project_id, "role": role}, ensure_ascii=False),
    ))
    await db.commit()

    return success_response(msg=f"成员 {target.nickname or target.username} 已添加", data=_serialize_member(member, target))


@router.put("/projects/{project_id}/members/{member_user_id}")
async def update_project_member(
    project_id: int,
    member_user_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:edit"))],
):
    """修改成员角色与权限。"""
    await _get_project_or_404(db, project_id)

    member = (
        await db.execute(
            select(WorkspaceProjectMember).where(
                WorkspaceProjectMember.project_id == project_id,
                WorkspaceProjectMember.user_id == member_user_id,
            )
        )
    ).scalars().first()
    if not member:
        raise NotFoundException("该用户不是项目成员")

    role = str(body.get("role") or member.role).lower()
    if role not in MEMBER_ROLES:
        raise ValidationException("项目角色无效")

    permissions = body.get("permissions", json.loads(member.permissions or "[]"))
    if not isinstance(permissions, list) or len(permissions) > 100:
        raise ValidationException("权限必须是数组且不超过100项")
    valid_perms = {v for v, _ in AVAILABLE_PERMISSIONS}
    bad = [p for p in permissions if str(p) not in valid_perms]
    if bad:
        raise ValidationException(f"无效权限点: {bad}")

    member.role = role
    member.permissions = json.dumps([str(p) for p in permissions], ensure_ascii=False) if permissions else "[]"
    await db.commit()

    from src.plugins.builtin.aegis_agent.security_models import UserActionLog
    db.add(UserActionLog(
        user_id=user.id, username=user.username, action="workspace.member.update",
        target_type="project_member", target_id=str(member_user_id),
        detail=json.dumps({"project_id": project_id, "role": role}, ensure_ascii=False),
    ))
    await db.commit()

    return success_response(msg="成员已更新", data={
        "user_id": member_user_id,
        "role": role,
        "permissions": _member_perm(role, member.permissions),
    })


@router.delete("/projects/{project_id}/members/{member_user_id}")
async def remove_project_member(
    project_id: int,
    member_user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:edit"))],
):
    """移除项目成员。"""
    project = await _get_project_or_404(db, project_id)

    if member_user_id == project.user_id:
        raise ValidationException("不能移除项目创建者")

    member = (
        await db.execute(
            select(WorkspaceProjectMember).where(
                WorkspaceProjectMember.project_id == project_id,
                WorkspaceProjectMember.user_id == member_user_id,
            )
        )
    ).scalars().first()
    if not member:
        raise NotFoundException("该用户不是项目成员")

    await db.delete(member)

    from src.plugins.builtin.aegis_agent.security_models import UserActionLog
    db.add(UserActionLog(
        user_id=user.id, username=user.username, action="workspace.member.remove",
        target_type="project_member", target_id=str(member_user_id),
        detail=json.dumps({"project_id": project_id, "project_name": project.name}, ensure_ascii=False),
    ))
    await db.commit()

    return success_response(msg="成员已移除")
