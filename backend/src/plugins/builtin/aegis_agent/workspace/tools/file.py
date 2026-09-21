"""文件操作工具——读/写/列/删/移动。

所有操作经过沙箱路径校验，确保在项目根目录内。
"""

import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
from typing import Any

from loguru import logger
from src.plugins.builtin.aegis_agent.workspace.sandbox import Sandbox, SandboxConfig

# ── 文件类型分类 ──
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"}
TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".ini", ".cfg", ".conf", ".toml",
    ".yaml", ".yml", ".json", ".xml", ".html", ".htm", ".css", ".scss", ".less",
    ".js", ".jsx", ".ts", ".tsx", ".vue", ".py", ".rb", ".go", ".rs", ".java",
    ".kt", ".swift", ".c", ".cpp", ".cc", ".h", ".hpp", ".cs", ".php", ".pl",
    ".sh", ".bash", ".zsh", ".fish", ".bat", ".cmd", ".ps1", ".sql", ".graphql",
    ".dockerfile", ".env", ".gitignore", ".editorconfig", ".csv", ".tsv",
    ".lua", ".r", ".scala", ".groovy", ".gradle", ".makefile", ".cmake",
}
CODE_EXTS = {
    ".js", ".jsx", ".ts", ".tsx", ".vue", ".py", ".rb", ".go", ".rs", ".java",
    ".kt", ".swift", ".c", ".cpp", ".cc", ".h", ".hpp", ".cs", ".php", ".pl",
    ".sh", ".bash", ".zsh", ".sql", ".graphql", ".lua", ".r", ".scala",
    ".groovy", ".html", ".htm", ".css", ".scss", ".less",
}
MARKDOWN_EXTS = {".md", ".markdown", ".rst"}

# 预览大小限制
MAX_TEXT_PREVIEW_SIZE = 2 * 1024 * 1024      # 文本 2MB
MAX_IMAGE_PREVIEW_SIZE = 10 * 1024 * 1024     # 图片 10MB


def _classify_file(path: Path) -> str:
    """根据扩展名判断文件预览类型：image / text / markdown / binary"""
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in MARKDOWN_EXTS:
        return "markdown"
    if ext in TEXT_EXTS:
        return "text"
    # 无扩展名也尝试按文本处理（如 Dockerfile, Makefile 等）
    name = path.name.lower()
    if name in ("dockerfile", "makefile", "readme", "license"):
        return "text"
    # 用 mimetypes 辅助
    mime, _ = mimetypes.guess_type(str(path))
    if mime and mime.startswith("text/"):
        return "text"
    return "binary"


async def read_file(project_root: str, file_path: str) -> str:
    """读取文件内容（按类型返回：文本/Markdown/图片 base64/二进制拦截）。

    Args:
        project_root: 项目根目录绝对路径
        file_path: 相对项目根的文件路径
    """
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

        size = path.stat().st_size
        file_type = _classify_file(path)
        ext = path.suffix.lower()

        # ── 图片：返回 base64 ──
        if file_type == "image":
            if size > MAX_IMAGE_PREVIEW_SIZE:
                return json.dumps({
                    "path": file_path,
                    "file_type": "image",
                    "size": size,
                    "preview_type": "image_too_large",
                    "mime": mimetypes.guess_type(str(path))[0] or "image/*",
                }, ensure_ascii=False)
            raw = path.read_bytes()
            mime = mimetypes.guess_type(str(path))[0] or "image/*"
            b64 = base64.b64encode(raw).decode("ascii")
            return json.dumps({
                "path": file_path,
                "file_type": "image",
                "preview_type": "image",
                "content": f"data:{mime};base64,{b64}",
                "size": size,
                "mime": mime,
            }, ensure_ascii=False)

        # ── 二进制文件：不读取内容 ──
        if file_type == "binary":
            return json.dumps({
                "path": file_path,
                "file_type": "binary",
                "preview_type": "binary",
                "size": size,
                "ext": ext,
            }, ensure_ascii=False)

        # ── 文本/Markdown：读取内容 ──
        if size > MAX_TEXT_PREVIEW_SIZE:
            return json.dumps({
                "path": file_path,
                "file_type": file_type,
                "preview_type": "text_too_large",
                "size": size,
            }, ensure_ascii=False)

        content = path.read_text(encoding="utf-8", errors="replace")
        content_hash = hashlib.md5(content.encode()).hexdigest()

        return json.dumps({
            "path": file_path,
            "file_type": file_type,
            "preview_type": file_type,
            "content": content,
            "size": size,
            "hash": content_hash,
            "lines": content.count("\n") + 1,
            "ext": ext,
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
    import difflib
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
        old_content = ""
        if path.exists():
            old_content = path.read_text(encoding="utf-8", errors="replace")
            old_hash = hashlib.md5(old_content.encode()).hexdigest()

        path.write_text(content, encoding="utf-8")
        new_hash = hashlib.md5(content.encode()).hexdigest()

        # 生成统一 diff（新文件无旧内容，diff 即全部新增行）
        diff_lines = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=file_path,
            tofile=file_path,
            lineterm="",
        ))
        diff_text = "".join(diff_lines)
        # 简化：统计变更统计（新增/删除行数）
        added = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))

        return json.dumps({
            "path": file_path,
            "action": "created" if old_hash is None else "modified",
            "old_hash": old_hash,
            "new_hash": new_hash,
            "size": len(content),
            "diff": diff_text,
            "diff_stats": {
                "added": added,
                "removed": removed,
                "total": added + removed,
            },
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
