"""AegisCode 工作区 API 路由。

路由前缀: /aegis-workspace
权限标识: aegis_agent:workspace:*

接口:
- POST   /projects           创建项目
- GET    /projects           项目列表
- GET    /projects/{id}      项目详情
- PUT    /projects/{id}      更新项目
- DELETE /projects/{id}      删除项目
- GET    /projects/{id}/files  文件列表
- GET    /projects/{id}/files/read  读取文件内容
- POST   /projects/{id}/files/write  写入文件内容
- POST   /projects/{id}/files/upload  上传文件（multipart，可指定文件夹，默认用户上传）
- DELETE /projects/{id}/files  删除文件（沙箱内，目录需为空）
- POST   /projects/{id}/folders  创建文件夹
- DELETE /projects/{id}/folders  删除文件夹（非空拒绝）
- GET    /projects/{id}/folders  文件夹列表（含排序）
- POST   /projects/{id}/folders/reorder  文件夹排序
- POST   /projects/{id}/execute  执行命令
- POST   /projects/{id}/snapshot  创建快照
- GET    /projects/{id}/snapshots 快照列表
- POST   /projects/{id}/snapshots/{sid}/review 审阅快照
"""

import json
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import delete, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user, require_permission
from src.core.exceptions import NotFoundException, ValidationException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.aegis_agent.workspace.models import (
    WorkspaceExecution,
    WorkspaceFile,
    WorkspaceProject,
    WorkspaceSnapshot,
)
from src.plugins.builtin.aegis_agent.workspace.sandbox import Sandbox, SandboxConfig
from src.plugins.builtin.aegis_agent.workspace.schemas import (
    ExecutionOut,
    FileOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    SnapshotOut,
)
from src.plugins.builtin.aegis_agent.workspace.git_manager import GitManager

router = APIRouter(prefix="/aegis-workspace", tags=["AegisCode 工作区"])


# ---------------------------------------------------------------------------
# 项目 CRUD
# ---------------------------------------------------------------------------

@router.post("/projects")
async def create_project(
    body: ProjectCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:create"))],
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
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:list"))],
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
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:list"))],
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
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:edit"))],
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
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:delete"))],
):
    """删除项目（标记删除，不删磁盘文件）。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    project.status = "deleted"
    await db.commit()
    return success_response(msg="项目已删除")


@router.get("/projects/{project_id}/stats")
async def get_project_stats(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:list"))],
):
    """项目统计（右侧项目管理面板）。

    返回:
    - token: 总Token/会话数/消息数（聚合本项目所有 AgentRun + AgentUsageLog）
    - files: 文件数/总大小（磁盘递归统计，跳过 .git）
    - run 集计来自 aegis_agent_runs（workspace_id 关联）
    """
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    from src.plugins.builtin.aegis_agent.models import AgentRun, AgentStep, AgentUsageLog

    # ── Token 用量：run 集计 + usage_log 精确值 ──
    run_stmt = select(AgentRun).where(AgentRun.workspace_id == project_id)
    runs = (await db.execute(run_stmt)).scalars().all()
    run_ids = [r.id for r in runs]

    total_input = sum(r.total_input_tokens for r in runs)
    total_output = sum(r.total_output_tokens for r in runs)
    total_tokens = total_input + total_output

    if run_ids:
        usage_stmt = select(
            func.coalesce(func.sum(AgentUsageLog.input_tokens), 0),
            func.coalesce(func.sum(AgentUsageLog.output_tokens), 0),
        ).where(AgentUsageLog.run_id.in_(run_ids))
        u_in, u_out = (await db.execute(usage_stmt)).one()
        total_tokens = int(u_in or 0) + int(u_out or 0) or total_tokens

    message_count = (
        await db.execute(
            select(func.count())
            .select_from(AgentStep)
            .where(AgentStep.run_id.in_(run_ids), AgentStep.step_type == "llm_call")
            if run_ids
            else select(func.count()).select_from(AgentRun).where(true() == False)  # noqa: E712 空集哨兵
        )
    ).scalar() or 0

    # ── 文件存储：磁盘递归统计（跳过 .git）──
    file_count = 0
    total_size = 0
    root = Path(project.root_path) if project.root_path else None
    if root and root.is_dir():
        for p in root.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                try:
                    file_count += 1
                    total_size += p.stat().st_size
                except OSError:
                    pass

    return success_response(data={
        "token": {
            "total_tokens": total_tokens,
            "session_count": len(runs),
            "message_count": message_count,
        },
        "files": {
            "file_count": file_count,
            "total_size": total_size,
        },
    })


# ---------------------------------------------------------------------------
# 文件操作
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/files")
async def list_files(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:list"))],
    path: str = Query(default="."),
    recursive: bool = Query(default=False),
):
    """列出项目文件。

    recursive=true 时递归返回所有文件（相对路径，跳过 .git 与隐藏目录），
    供文件管理面板三分类展示；否则按目录列一层。
    """
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    if recursive:
        from src.plugins.builtin.aegis_agent.workspace.sandbox import Sandbox, SandboxConfig
        sandbox = Sandbox(SandboxConfig(root_path=project.root_path))
        valid, resolved = sandbox.validate_path(path)
        if not valid:
            raise ValidationException(resolved)
        base = Path(resolved)
        if not base.is_dir():
            raise ValidationException(f"不是目录: {path}")
        entries: list[dict] = []
        for p in base.rglob("*"):
            if ".git" in p.parts or any(part.startswith(".") for part in p.relative_to(base).parts):
                continue
            rel = str(p.relative_to(base))
            if p.is_dir():
                entries.append({"name": p.name, "path": rel, "type": "dir", "size": 0})
            else:
                try:
                    entries.append({"name": p.name, "path": rel, "type": "file", "size": p.stat().st_size})
                except OSError:
                    pass
        entries.sort(key=lambda e: (e["type"] != "dir", e["path"]))
        return success_response(data={"path": path, "items": entries, "total": len(entries), "recursive": True})

    from src.plugins.builtin.aegis_agent.workspace.tools.file import list_directory
    result = await list_directory(project.root_path, path)
    return success_response(data=json.loads(result))


@router.get("/projects/{project_id}/files/read")
async def read_file(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:list"))],
    path: str = Query(),
):
    """读取项目内文件内容。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    from src.plugins.builtin.aegis_agent.workspace.tools.file import read_file as _read
    result = json.loads(await _read(project.root_path, path))
    if "error" in result:
        raise ValidationException(result["error"])
    return success_response(data=result)


@router.post("/projects/{project_id}/files/write")
async def write_file(
    project_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:edit"))],
):
    """写入项目内文件内容。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    file_path = body.get("path", "")
    content = body.get("content", "")
    if not file_path:
        raise ValidationException("文件路径不能为空")

    from src.plugins.builtin.aegis_agent.workspace.tools.file import write_file as _write
    result = json.loads(await _write(project.root_path, file_path, content))
    if "error" in result:
        raise ValidationException(result["error"])
    return success_response(data=result, msg="文件已保存")


# ---------------------------------------------------------------------------
# 文件上传
# ---------------------------------------------------------------------------

# 上传大小限制：单文件 20MB
MAX_UPLOAD_SIZE = 20 * 1024 * 1024
# 危险扩展名黑名单（服务器侧不落盘可执行内容）
FORBIDDEN_EXTENSIONS = {".exe", ".sh", ".bat", ".cmd", ".com", ".scr", ".msi", ".app", ".dmg", ".jar"}


@router.post("/projects/{project_id}/files/upload")
async def upload_file(
    project_id: int,
    file: UploadFile = File(...),
    folder: str = Form(default="用户上传"),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:edit"))] = None,
):
    """上传文件到项目指定文件夹（默认「用户上传」）。

    multipart: file + folder（可选，默认 用户上传）
    """
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")

    if not project.root_path:
        raise ValidationException("项目未启用云存储目录")

    # 文件名校验：去路径分隔符 + 禁止危险扩展
    raw_name = Path(file.filename or "unnamed").name
    if not raw_name or raw_name.startswith("."):
        raise ValidationException("无效的文件名")
    if Path(raw_name).suffix.lower() in FORBIDDEN_EXTENSIONS:
        raise ValidationException(f"不支持的文件类型: {Path(raw_name).suffix}")

    # folder 校验：仅允许单层中文名/字母数字（防目录穿越）
    folder = (folder or "用户上传").strip()
    if not re.fullmatch(r"[\w\u4e00-\u9fa5-]+", folder):
        raise ValidationException("文件夹名不合法")
    if folder in (".", "..") or folder.startswith("."):
        raise ValidationException("文件夹名不合法")

    # 读内容 + 大小限制
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise ValidationException("文件大小超过 20MB 限制")
    if not content:
        raise ValidationException("文件内容为空")

    # 落盘：folder/文件名（沙箱内路径校验）
    sandbox = Sandbox(SandboxConfig(root_path=project.root_path))
    rel_path = f"{folder}/{raw_name}"
    valid, resolved = sandbox.validate_path(rel_path)
    if not valid:
        raise ValidationException(resolved)

    dest = Path(resolved)
    # 同名覆盖提示：返回明确的 overwritten 标记
    overwritten = dest.exists()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)

    return success_response(data={
        "path": rel_path,
        "name": raw_name,
        "folder": folder,
        "size": len(content),
        "overwritten": overwritten,
    }, msg="上传成功")


@router.delete("/projects/{project_id}/files")
async def delete_project_file(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:edit"))],
    path: str = Query(),
):
    """删除项目内文件（沙箱内路径校验；目录仅允许删空目录）。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")
    if not project.root_path:
        raise ValidationException("项目未启用云存储目录")

    if not path or not path.strip():
        raise ValidationException("文件路径不能为空")

    # 禁止删除项目根或穿越到根
    if path.strip() in (".", "", "/"):
        raise ValidationException("非法路径")

    from src.plugins.builtin.aegis_agent.workspace.tools.file import delete_file as _delete
    result = json.loads(await _delete(project.root_path, path))
    if "error" in result:
        raise ValidationException(result["error"])
    return success_response(data=result, msg="文件已删除")


# ---------------------------------------------------------------------------
# 文件夹管理
# ---------------------------------------------------------------------------

ORDER_FILE = ".folder-order.json"


def _load_folder_order(root_path: str) -> list[str]:
    """读取文件夹排序（项目根下的 .folder-order.json）。"""
    f = Path(root_path) / ORDER_FILE
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_folder_order(root_path: str, order: list[str]) -> None:
    f = Path(root_path) / ORDER_FILE
    f.write_text(json.dumps(order, ensure_ascii=False), encoding="utf-8")


def _list_real_folders(root_path: str) -> list[dict]:
    """列出项目根下的真实文件夹（跳过隐藏目录和 .git）。"""
    root = Path(root_path)
    if not root.is_dir():
        return []
    result = []
    for p in sorted(root.iterdir(), key=lambda e: e.name):
        if not p.is_dir() or p.name.startswith(".") or p.name == ".git":
            continue
        try:
            file_count = sum(1 for _ in p.rglob("*") if _.is_file() and ".git" not in _.parts)
        except OSError:
            file_count = 0
        result.append({"name": p.name, "file_count": file_count})
    return result


@router.get("/projects/{project_id}/folders")
async def list_folders(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:list"))],
):
    """列出项目文件夹（含文件数与排序）。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")
    if not project.root_path:
        raise ValidationException("项目未启用云存储目录")

    folders = _list_real_folders(project.root_path)
    order = _load_folder_order(project.root_path)

    # 按排序文件排：有序的在前（按 order 序），未记录的按名称序追加在后
    def sort_key(f: dict):
        name = f["name"]
        return (0, order.index(name)) if name in order else (1, name)

    folders.sort(key=sort_key)
    return success_response(data={"folders": folders, "order": order})


@router.post("/projects/{project_id}/folders")
async def create_folder(
    project_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:edit"))],
):
    """创建文件夹。请求体: {"name": "新文件夹"}"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")
    if not project.root_path:
        raise ValidationException("项目未启用云存储目录")

    name = (body.get("name") or "").strip()
    if not name or len(name) > 30:
        raise ValidationException("文件夹名需为 1-30 个字符")
    if not re.fullmatch(r"[\w\u4e00-\u9fa5-]+", name):
        raise ValidationException("文件夹名仅支持中文/字母/数字/下划线/连字符")

    root = Path(project.root_path)
    target = root / name
    if target.exists():
        raise ValidationException(f"文件夹已存在: {name}")

    sandbox = Sandbox(SandboxConfig(root_path=project.root_path))
    valid, resolved = sandbox.validate_path(name)
    if not valid:
        raise ValidationException(resolved)

    target.mkdir(parents=False, exist_ok=False)
    return success_response(data={"name": name}, msg="文件夹已创建")


@router.delete("/projects/{project_id}/folders")
async def delete_folder(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:edit"))],
    name: str = Query(),
):
    """删除文件夹（仅允许删空文件夹；默认三分类文件夹不可删）。"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")
    if not project.root_path:
        raise ValidationException("项目未启用云存储目录")

    name = (name or "").strip()
    if not name:
        raise ValidationException("文件夹名不能为空")
    if name in ("AI生成文档", "AI编程", "用户上传"):
        raise ValidationException("默认分类文件夹不可删除")

    sandbox = Sandbox(SandboxConfig(root_path=project.root_path))
    valid, resolved = sandbox.validate_path(name)
    if not valid:
        raise ValidationException(resolved)

    target = Path(resolved)
    if not target.exists() or not target.is_dir():
        raise NotFoundException("文件夹不存在")
    if any(target.iterdir()):
        raise ValidationException("文件夹非空，请先清空文件")

    target.rmdir()

    # 同步清理排序记录
    order = _load_folder_order(project.root_path)
    if name in order:
        order.remove(name)
        _save_folder_order(project.root_path, order)

    return success_response(msg="文件夹已删除")


@router.post("/projects/{project_id}/folders/reorder")
async def reorder_folders(
    project_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:edit"))],
):
    """文件夹排序。请求体: {"order": ["用户上传", "AI生成文档", "AI编程"]}"""
    project = await db.get(WorkspaceProject, project_id)
    if not project:
        raise NotFoundException("项目不存在")
    if not project.root_path:
        raise ValidationException("项目未启用云存储目录")

    order = body.get("order")
    if not isinstance(order, list) or not all(isinstance(n, str) for n in order):
        raise ValidationException("order 需为字符串数组")

    # 校验：必须与现有文件夹集合一致（防删除/伪造）
    existing = {f["name"] for f in _list_real_folders(project.root_path)}
    if set(order) != existing or len(order) != len(existing):
        raise ValidationException("排序列表与现有文件夹不一致，请刷新后重试")

    _save_folder_order(project.root_path, order)
    return success_response(data={"order": order}, msg="排序已保存")


# ---------------------------------------------------------------------------
# 命令执行
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/execute")
async def execute_command(
    project_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:execute"))],
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
    from src.plugins.builtin.aegis_agent.workspace.tools.command import execute_command as _exec
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
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:snapshot"))],
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
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:list"))],
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
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:snapshot"))],
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
    user: Annotated[User, Depends(require_permission("aegis_agent:workspace:projects:list"))],
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
