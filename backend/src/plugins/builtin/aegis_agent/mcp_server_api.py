"""MCP 服务器管理 API。

路由前缀: /aegis-mcp
权限标识: aegis_mcp:*
"""

import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sql_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.crypto import decrypt_api_key, encrypt_api_key, mask_api_key
from src.core.deps import require_permission
from src.core.exceptions import ConflictException, NotFoundException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.aegis_agent.mcp_server_models import McpServer

router = APIRouter(prefix="/aegis-mcp", tags=["MCP 服务器管理"])


def _load_json(text: str | None, default):
    try:
        return json.loads(text) if text else default
    except (json.JSONDecodeError, TypeError):
        return default


def _server_to_dict(s: McpServer) -> dict:
    try:
        masked = mask_api_key(decrypt_api_key(s.api_key_enc)) if s.api_key_enc else ""
    except Exception:
        masked = "****" if s.api_key_enc else ""
    return {
        "id": s.id,
        "name": s.name,
        "display_name": s.display_name,
        "description": s.description,
        "server_url": s.server_url,
        "server_type": s.server_type,
        "api_key_masked": masked,
        "tools": _load_json(s.tools, []),
        "is_active": s.is_active,
        "sort_order": s.sort_order,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/servers")
async def list_servers(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_mcp:list"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    server_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    """MCP 服务器列表（分页）。"""
    stmt = select(McpServer).order_by(McpServer.sort_order, McpServer.id)
    if server_type:
        stmt = stmt.where(McpServer.server_type == server_type)
    if is_active is not None:
        stmt = stmt.where(McpServer.is_active == is_active)

    count_stmt = select(sql_func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()

    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_server_to_dict(s) for s in items],
    })


@router.post("/servers")
async def create_server(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_mcp:add"))],
):
    """创建 MCP 服务器。"""
    name = body.get("name", "").strip()
    if not name:
        raise ConflictException("服务器名称不能为空")

    exists = (
        await db.execute(select(McpServer).where(McpServer.name == name))
    ).scalar_one_or_none()
    if exists:
        raise ConflictException(f"服务器 '{name}' 已存在")

    server = McpServer(
        name=name,
        display_name=body.get("display_name") or name,
        description=body.get("description", ""),
        server_url=body.get("server_url", ""),
        server_type=body.get("server_type", "sse"),
        api_key_enc=encrypt_api_key(body["api_key"]) if body.get("api_key") else "",
        tools=json.dumps(body.get("tools", []), ensure_ascii=False),
        is_active=body.get("is_active", True),
        sort_order=body.get("sort_order", 0),
    )
    db.add(server)
    await db.commit()
    return success_response(data={"id": server.id}, msg="创建成功")


@router.put("/servers/{server_id}")
async def update_server(
    server_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_mcp:edit"))],
):
    """更新 MCP 服务器。"""
    server = await db.get(McpServer, server_id)
    if not server:
        raise NotFoundException("服务器不存在")

    if "name" in body and body["name"] != server.name:
        exists = (
            await db.execute(select(McpServer).where(McpServer.name == body["name"]))
        ).scalar_one_or_none()
        if exists:
            raise ConflictException(f"服务器 '{body['name']}' 已存在")
        server.name = body["name"]

    simple_fields = ["display_name", "description", "server_url", "server_type", "is_active", "sort_order"]
    for field in simple_fields:
        if field in body:
            setattr(server, field, body[field])

    if body.get("api_key"):
        server.api_key_enc = encrypt_api_key(body["api_key"])

    if "tools" in body:
        server.tools = json.dumps(body["tools"], ensure_ascii=False)

    await db.commit()
    return success_response(msg="更新成功")


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_mcp:delete"))],
):
    """删除 MCP 服务器。"""
    server = await db.get(McpServer, server_id)
    if not server:
        raise NotFoundException("服务器不存在")
    await db.delete(server)
    await db.commit()
    return success_response(msg="删除成功")


@router.post("/servers/{server_id}/test")
async def test_server(
    server_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_mcp:list"))],
):
    """测试 MCP 服务器连通性（HTTP 探测 server_url）。"""
    import httpx

    server = await db.get(McpServer, server_id)
    if not server:
        raise NotFoundException("服务器不存在")

    if not server.server_url:
        return success_response(data={"ok": False, "error": "未配置服务器地址"}, msg="测试失败")

    try:
        headers = {}
        if server.api_key_enc:
            headers["Authorization"] = f"Bearer {decrypt_api_key(server.api_key_enc)}"
        async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
            resp = await client.get(server.server_url, headers=headers)
            return success_response(
                data={"ok": resp.status_code < 400, "status_code": resp.status_code},
                msg="测试完成",
            )
    except Exception as e:
        return success_response(data={"ok": False, "error": str(e)}, msg="测试失败")
