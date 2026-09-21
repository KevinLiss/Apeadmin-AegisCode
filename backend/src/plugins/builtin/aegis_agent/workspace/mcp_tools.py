"""AegisCode 工作区 MCP 工具注册。

注册工作区操作相关的 MCP 工具，让 AI Agent 能操作文件和执行命令。
"""

import json
from typing import Any

from loguru import logger
from sqlalchemy import select

from src.db import SessionLocal
from src.mcp import mcp_manager
from src.plugins.builtin.aegis_agent.workspace.models import WorkspaceProject
from src.plugins.builtin.aegis_agent.workspace.tools.file import (
    read_file,
    write_file,
    list_directory,
    delete_file,
    move_file,
)
from src.plugins.builtin.aegis_agent.workspace.tools.command import execute_command
from src.plugins.builtin.aegis_agent.workspace.tools.search import search_code
from src.plugins.builtin.aegis_agent.workspace.tools.todo import aegis_todo_list, aegis_todo_write


# ---------------------------------------------------------------------------
# 辅助：获取项目根路径
# ---------------------------------------------------------------------------

async def _get_project_root(project_id: int) -> str:
    """从数据库获取项目根路径。"""
    async with SessionLocal() as db:
        project = await db.get(WorkspaceProject, project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")
        return project.root_path


# ---------------------------------------------------------------------------
# 文件工具
# ---------------------------------------------------------------------------

async def _aegis_read_file(project_id: int, file_path: str) -> str:
    """读取项目中的文件内容。

    Args:
        project_id: 项目ID
        file_path: 文件路径（相对项目根目录）
    """
    root = await _get_project_root(project_id)
    return await read_file(root, file_path)


async def _aegis_write_file(project_id: int, file_path: str, content: str) -> str:
    """写入或创建项目中的文件。

    Args:
        project_id: 项目ID
        file_path: 文件路径（相对项目根目录）
        content: 文件内容
    """
    root = await _get_project_root(project_id)
    return await write_file(root, file_path, content)


async def _aegis_list_directory(project_id: int, dir_path: str = ".") -> str:
    """列出项目目录内容。

    Args:
        project_id: 项目ID
        dir_path: 目录路径（相对项目根目录），默认为根目录
    """
    root = await _get_project_root(project_id)
    return await list_directory(root, dir_path)


async def _aegis_delete_file(project_id: int, file_path: str) -> str:
    """删除项目中的文件。

    Args:
        project_id: 项目ID
        file_path: 文件路径（相对项目根目录）
    """
    root = await _get_project_root(project_id)
    return await delete_file(root, file_path)


async def _aegis_move_file(project_id: int, src_path: str, dst_path: str) -> str:
    """移动或重命名项目中的文件。

    Args:
        project_id: 项目ID
        src_path: 源文件路径
        dst_path: 目标文件路径
    """
    root = await _get_project_root(project_id)
    return await move_file(root, src_path, dst_path)


# ---------------------------------------------------------------------------
# 命令工具
# ---------------------------------------------------------------------------

async def _aegis_execute_command(
    project_id: int,
    command: str,
    cwd: str = ".",
    timeout: int = 60,
) -> str:
    """在项目沙箱内执行 shell 命令。

    Args:
        project_id: 项目ID
        command: 要执行的命令
        cwd: 工作目录（相对项目根），默认为根目录
        timeout: 超时秒数，默认 60
    """
    root = await _get_project_root(project_id)
    return await execute_command(root, command, cwd, timeout)


# ---------------------------------------------------------------------------
# 搜索工具
# ---------------------------------------------------------------------------

async def _aegis_search_code(
    project_id: int,
    pattern: str,
    file_pattern: str = "*",
    use_regex: bool = False,
) -> str:
    """在项目内搜索代码。

    Args:
        project_id: 项目ID
        pattern: 搜索模式（文本或正则）
        file_pattern: 文件名过滤（glob），默认所有文件
        use_regex: 是否使用正则表达式，默认为 False
    """
    root = await _get_project_root(project_id)
    return await search_code(root, pattern, file_pattern, use_regex=use_regex)


# ---------------------------------------------------------------------------
# 项目管理工具
# ---------------------------------------------------------------------------

async def _aegis_list_projects(status: str | None = None) -> str:
    """列出手作区项目。

    Args:
        status: 筛选状态（active/archived/deleted），留空返回全部
    """
    async with SessionLocal() as db:
        stmt = select(WorkspaceProject).order_by(WorkspaceProject.id.desc())
        if status:
            stmt = stmt.where(WorkspaceProject.status == status)
        projects = (await db.execute(stmt)).scalars().all()

    items = [
        {"id": p.id, "name": p.name, "root_path": p.root_path, "status": p.status}
        for p in projects
    ]
    return json.dumps({"total": len(items), "items": items}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------

def register_aegis_workspace_mcp_tools() -> None:
    """注册工作区 MCP 工具。"""
    # 文件工具
    mcp_manager.register_tool("aegis_read_file", "读取项目文件内容", _aegis_read_file, plugin_name="aegis_agent", category="aegis_agent")
    mcp_manager.register_tool("aegis_write_file", "写入或创建项目文件", _aegis_write_file, plugin_name="aegis_agent", category="aegis_agent")
    mcp_manager.register_tool("aegis_list_directory", "列出项目目录内容", _aegis_list_directory, plugin_name="aegis_agent", category="aegis_agent")
    mcp_manager.register_tool("aegis_delete_file", "删除项目文件", _aegis_delete_file, plugin_name="aegis_agent", category="aegis_agent")
    mcp_manager.register_tool("aegis_move_file", "移动或重命名项目文件", _aegis_move_file, plugin_name="aegis_agent", category="aegis_agent")

    # 命令工具
    mcp_manager.register_tool("aegis_execute_command", "在项目沙箱内执行 shell 命令", _aegis_execute_command, plugin_name="aegis_agent", category="aegis_agent")

    # 搜索工具
    mcp_manager.register_tool("aegis_search_code", "在项目内搜索代码", _aegis_search_code, plugin_name="aegis_agent", category="aegis_agent")

    # 项目管理
    mcp_manager.register_tool("aegis_list_projects", "列出工作区项目", _aegis_list_projects, plugin_name="aegis_agent", category="aegis_agent")

    # Todo 任务清单
    mcp_manager.register_tool("aegis_todo_write", "写入/更新 Agent 任务清单（todos）", aegis_todo_write, plugin_name="aegis_agent", category="aegis_agent")
    mcp_manager.register_tool("aegis_todo_list", "列出当前 Agent 任务清单", aegis_todo_list, plugin_name="aegis_agent", category="aegis_agent")

    logger.info("Registered 10 aegis workspace MCP tools")
