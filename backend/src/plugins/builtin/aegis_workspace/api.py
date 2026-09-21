"""AegisCode 工作区 API 路由。

路由前缀: /aegis-workspace
权限标识: aegis_workspace:*

接口:
- POST   /projects           创建项目
- GET    /projects           项目列表
- GET    /projects/{id}      项目详情
- PUT    /projects/{id}      更新项目
- DELETE /projects/{id}      删除项目
- GET    /projects/{id}/files  文件列表
- GET    /projects/{id}/files/read  读取文件内容
- POST   /projects/{id}/files/write  写入文件内容
- POST   /projects/{id}/execute  执行命令
- POST   /projects/{id}/snapshot  创建快照
- GET    /projects/{id}/snapshots 快照列表
- POST   /projects/{id}/snapshots/{sid}/review 审阅快照
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user, require_permission
from src.core.exceptions import NotFoundException, ValidationException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.aegis_workspace.models import (
    WorkspaceExecution,
    WorkspaceFile,
    WorkspaceProject,
    WorkspaceSnapshot,
)
from src.plugins.builtin.aegis_workspace.sandbox import Sandbox, SandboxConfig
from src.plugins.builtin.aegis_workspace.schemas import (
    ExecutionOut,
    FileOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    SnapshotOut,
)
from src.plugins.builtin.aegis_workspace.git_manager import GitManager

router = APIRouter(prefix="/aegis-workspace", tags=["AegisCode 工作区"])


# ---------------------------------------------------------------------------
# 项目 CRUD
# ---------------------------------------------------------------------------

@router.post("/projects")
async def create_project(
    body: ProjectCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:projects:create"))],
):
    """创建工作区项目。

    - cloud 模式: 后端自动生成沙盒目录 {CLOUD_STORAGE_DIR}/user{id}_project{id}
    - local 模式: root_path 留空, 仅存 root_hint 展示名, 真实路径只存桌面端加密 store
    """
    import os
    from pathlib import Path

    # 安全: local 模式需要桌面端标识 (预留, Web 端只能创建 cloud)
    # TODO: 后续加 X-Client-Type header 校验

    # 先创建记录拿到自增 ID
    project = WorkspaceProject(
        user_id=user.id,
        name=body.name,
        description=body.description,
        root_path="",  # 延迟填充
        storage_type=body.storage_type,
        root_hint=body.root_hint if body.storage_type == "local" else None,
        git_enabled=body.git_enabled,
        sandbox_enabled=body.sandbox_enabled,
        allowed_paths=json.dumps(body.allowed_paths, ensure_ascii=False) if body.allowed_paths else None,
        blocked_commands=json.dumps(body.blocked_commands, ensure_ascii=False) if body.blocked_commands else None,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    if body.storage_type == "cloud":
        # 云端: 后端自动生成沙盒目录
        from src.core.config import settings
        storage_dir = Path(settings.FILE_STORAGE_DIR).parent / "cloud_projects"
        storage_dir.mkdir(parents=True, exist_ok=True)
        project_path = storage_dir / f"user{user.id}_project{project.id}"
        project_path.mkdir(parents=True, exist_ok=True)

        # 创建 3 个默认子目录
        for subdir in ["AI生成文档", "AI编程", "用户上传"]:
            (project_path / subdir).mkdir(exist_ok=True)

        project.root_path = str(project_path.resolve())

        # Git 初始化
        if body.git_enabled:
            git = GitManager(project.root_path)
            await git.ensure_repo()
    # local 模式: root_path 保持空字符串, 真实路径不上传服务器

    await db.commit()
    await db.refresh(project)

    return success_response(data={"id": project.id, "storage_type": project.storage_type}, msg="项目已创建")


@router.get("/projects")
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:projects:list"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
):
    """分页查询项目列表。"""
    stmt = select(WorkspaceProject).order_by(WorkspaceProject.id.desc())
    if status:
        stmt = stmt.where(WorkspaceProject.status == status)

    count_stmt = select(func.count()).select_from(WorkspaceProject)
    if status:
        count_stmt = count_stmt.where(WorkspaceProject.status == status)

    total = (await db.execute(count_stmt)).scalar() or 0
    items = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [ProjectOut.model_validate(p) for p in items],
    })


@router.get("/projects/{project_id}")
async def get_project(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:projects:list"))],
):
    """获取项目详情。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")
    return success_response(data=ProjectOut.model_validate(project).model_dump())


@router.put("/projects/{project_id}")
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:projects:edit"))],
):
    """更新项目配置。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    update_data = body.model_dump(exclude_unset=True)
    if "allowed_paths" in update_data and update_data["allowed_paths"] is not None:
        update_data["allowed_paths"] = json.dumps(update_data["allowed_paths"], ensure_ascii=False)
    if "blocked_commands" in update_data and update_data["blocked_commands"] is not None:
        update_data["blocked_commands"] = json.dumps(update_data["blocked_commands"], ensure_ascii=False)

    for key, value in update_data.items():
        setattr(project, key, value)

    await db.commit()
    return success_response(msg="更新成功")


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:projects:delete"))],
):
    """删除项目（标记删除，不删磁盘文件）。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    project.status = "deleted"
    await db.commit()
    return success_response(msg="项目已删除")


# ---------------------------------------------------------------------------
# 文件操作
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/files")
async def list_files(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:projects:list"))],
    path: str = Query(default="."),
):
    """列出项目文件。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    from src.plugins.builtin.aegis_workspace.tools.file import list_directory
    result = await list_directory(project.root_path, path)
    return success_response(data=json.loads(result))


@router.get("/projects/{project_id}/files/read")
async def read_file(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:projects:list"))],
    path: str = Query(),
):
    """读取项目内文件内容。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    from src.plugins.builtin.aegis_workspace.tools.file import read_file as _read
    result = json.loads(await _read(project.root_path, path))
    if "error" in result:
        raise ValidationException(result["error"])
    return success_response(data=result)


@router.post("/projects/{project_id}/files/write")
async def write_file(
    project_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:projects:edit"))],
):
    """写入项目内文件内容。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    file_path = body.get("path", "")
    content = body.get("content", "")
    if not file_path:
        raise ValidationException("文件路径不能为空")

    from src.plugins.builtin.aegis_workspace.tools.file import write_file as _write
    result = json.loads(await _write(project.root_path, file_path, content))
    if "error" in result:
        raise ValidationException(result["error"])
    return success_response(data=result, msg="文件已保存")


# ---------------------------------------------------------------------------
# 命令执行
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/execute")
async def execute_command(
    project_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:execute"))],
):
    """在项目沙箱内执行命令。

    请求体: {"command": "ls -la", "cwd": ".", "timeout": 60}
    """
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    command = body.get("command", "")
    cwd = body.get("cwd", ".")
    timeout = body.get("timeout", 60)

    if not command:
        raise ValidationException("命令不能为空")

    # 执行
    from src.plugins.builtin.aegis_workspace.tools.command import execute_command as _exec
    result_json = await _exec(project.root_path, command, cwd, timeout)
    result = json.loads(result_json)

    # 记录执行
    execution = WorkspaceExecution(
        project_id=project_id,
        command=command,
        cwd=cwd,
        exit_code=result.get("exit_code"),
        stdout=result.get("stdout"),
        stderr=result.get("stderr"),
        duration_ms=result.get("duration_ms"),
        blocked=result.get("blocked", False),
        block_reason=result.get("block_reason"),
    )
    db.add(execution)
    await db.commit()

    return success_response(data=result)


# ---------------------------------------------------------------------------
# Git 快照
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/snapshot")
async def create_snapshot(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:snapshot"))],
    body: dict | None = None,
):
    """创建 Git 快照。

    请求体（可选）: {"commit_message": "修复登录bug", "run_id": 1, "step_index": 5}
    """
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    if not project.git_enabled:
        raise ValidationException("项目未启用 Git")

    body = body or {}
    git = GitManager(project.root_path)
    snapshot = await git.create_snapshot(
        project_id=project_id,
        run_id=body.get("run_id"),
        step_index=body.get("step_index"),
        commit_message=body.get("commit_message", "auto snapshot"),
    )

    if not snapshot:
        return success_response(msg="无变更，跳过快照")

    return success_response(data={
        "commit_hash": snapshot.commit_hash,
        "commit_message": snapshot.commit_message,
        "files_changed": snapshot.files_changed,
    }, msg="快照已创建")


@router.get("/projects/{project_id}/snapshots")
async def list_snapshots(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:projects:list"))],
):
    """列出项目的 Git 快照。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    git = GitManager(project.root_path)
    snapshots = await git.list_snapshots(project_id)
    return success_response(data=snapshots)


@router.post("/projects/{project_id}/snapshots/{snapshot_id}/review")
async def review_snapshot(
    project_id: int,
    snapshot_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:snapshot"))],
):
    """审阅快照。

    请求体: {"status": "approved", "comment": "代码质量良好"}
    """
    snapshot = await db.get(WorkspaceSnapshot, snapshot_id)
    if not snapshot or snapshot.project_id != project_id:
        raise NotFoundException("快照不存在")

    snapshot.reviewed = True
    snapshot.review_status = body.get("status", "pending")
    snapshot.review_comment = body.get("comment")
    await db.commit()
    return success_response(msg="审阅已记录")


# ---------------------------------------------------------------------------
# 执行记录
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/executions")
async def list_executions(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_workspace:projects:list"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """列出项目的命令执行记录。"""
    stmt = (
        select(WorkspaceExecution)
        .where(WorkspaceExecution.project_id == project_id)
        .order_by(WorkspaceExecution.id.desc())
    )
    items = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return success_response(data=[ExecutionOut.model_validate(e) for e in items])
