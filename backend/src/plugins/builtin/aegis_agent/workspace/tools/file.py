"""文件操作工具——读/写/列/删/移动。

所有操作经过沙箱路径校验，确保在项目根目录内。
"""

import hashlib
import os
from pathlib import Path
from typing import Any

from loguru import logger
from src.plugins.builtin.aegis_agent.workspace.sandbox import Sandbox, SandboxConfig


async def read_file(project_root: str, file_path: str) -> str:
    """读取文件内容。

    Args:
        project_root: 项目根目录绝对路径
        file_path: 相对项目根的文件路径
    """
    import json

    sandbox = Sandbox(SandboxConfig(root_path=project_root))
    valid, resolved = sandbox.validate_path(file_path)
    if not valid:
        return json.dumps({"error": resolved}, ensure_ascii=False)

    try:
        path = Path(resolved)
        if not path.exists():
            return json.dumps({"error": f"文件不存在: {file_path}"}, ensure_ascii=False)
        if path.is_dir():
            return json.dumps({"error": f"是目录不是文件: {file_path}"}, ensure_ascii=False)

        content = path.read_text(encoding="utf-8", errors="replace")
        size = path.stat().st_size
        content_hash = hashlib.md5(content.encode()).hexdigest()

        return json.dumps({
            "path": file_path,
            "content": content,
            "size": size,
            "hash": content_hash,
            "lines": content.count("\n") + 1,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def write_file(project_root: str, file_path: str, content: str) -> str:
    """写入文件（覆盖或创建）。

    Args:
        project_root: 项目根目录绝对路径
        file_path: 相对项目根的文件路径
        content: 文件内容
    """
    import json

    sandbox = Sandbox(SandboxConfig(root_path=project_root))
    valid, resolved = sandbox.validate_path(file_path)
    if not valid:
        return json.dumps({"error": resolved}, ensure_ascii=False)

    try:
        path = Path(resolved)
        # 自动创建父目录
        path.parent.mkdir(parents=True, exist_ok=True)

        # 如果文件已存在，记录旧内容
        old_hash = None
        if path.exists():
            old_content = path.read_text(encoding="utf-8", errors="replace")
            old_hash = hashlib.md5(old_content.encode()).hexdigest()

        path.write_text(content, encoding="utf-8")
        new_hash = hashlib.md5(content.encode()).hexdigest()

        return json.dumps({
            "path": file_path,
            "action": "created" if old_hash is None else "modified",
            "old_hash": old_hash,
            "new_hash": new_hash,
            "size": len(content),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def list_directory(project_root: str, dir_path: str = ".", max_items: int = 200) -> str:
    """列出目录内容。

    Args:
        project_root: 项目根目录绝对路径
        dir_path: 相对项目根的目录路径，默认为根目录
        max_items: 最大返回条目数
    """
    import json

    sandbox = Sandbox(SandboxConfig(root_path=project_root))
    valid, resolved = sandbox.validate_path(dir_path)
    if not valid:
        return json.dumps({"error": resolved}, ensure_ascii=False)

    try:
        path = Path(resolved)
        if not path.exists():
            return json.dumps({"error": f"目录不存在: {dir_path}"}, ensure_ascii=False)
        if not path.is_dir():
            return json.dumps({"error": f"不是目录: {dir_path}"}, ensure_ascii=False)

        items: list[dict] = []
        for entry in sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name)):
            if entry.name.startswith("."):
                continue
            items.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
            if len(items) >= max_items:
                items.append({"name": "...", "type": "truncated"})
                break

        return json.dumps({
            "path": dir_path,
            "items": items,
            "total": len(items),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def delete_file(project_root: str, file_path: str) -> str:
    """删除文件或空目录。

    Args:
        project_root: 项目根目录绝对路径
        file_path: 相对项目根的文件路径
    """
    import json

    sandbox = Sandbox(SandboxConfig(root_path=project_root))
    valid, resolved = sandbox.validate_path(file_path)
    if not valid:
        return json.dumps({"error": resolved}, ensure_ascii=False)

    try:
        path = Path(resolved)
        if not path.exists():
            return json.dumps({"error": f"文件不存在: {file_path}"}, ensure_ascii=False)

        if path.is_dir():
            # 目录只删空目录
            if any(path.iterdir()):
                return json.dumps({"error": "目录非空，拒绝删除"}, ensure_ascii=False)
            path.rmdir()
        else:
            path.unlink()

        return json.dumps({"path": file_path, "action": "deleted"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def move_file(project_root: str, src_path: str, dst_path: str) -> str:
    """移动/重命名文件。

    Args:
        project_root: 项目根目录绝对路径
        src_path: 源文件路径
        dst_path: 目标文件路径
    """
    import json

    sandbox = Sandbox(SandboxConfig(root_path=project_root))
    valid_src, resolved_src = sandbox.validate_path(src_path)
    if not valid_src:
        return json.dumps({"error": f"源路径无效: {resolved_src}"}, ensure_ascii=False)

    valid_dst, resolved_dst = sandbox.validate_path(dst_path)
    if not valid_dst:
        return json.dumps({"error": f"目标路径无效: {resolved_dst}"}, ensure_ascii=False)

    try:
        src = Path(resolved_src)
        dst = Path(resolved_dst)
        if not src.exists():
            return json.dumps({"error": f"源文件不存在: {src_path}"}, ensure_ascii=False)

        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)

        return json.dumps({
            "action": "moved",
            "src": src_path,
            "dst": dst_path,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
