"""代码搜索工具——grep/ripgrep/正则搜索。"""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

from src.plugins.builtin.aegis_agent.workspace.sandbox import Sandbox, SandboxConfig


async def search_code(
    project_root: str,
    pattern: str,
    file_pattern: str = "*",
    max_results: int = 50,
    use_regex: bool = False,
) -> str:
    """在项目内搜索代码。

    Args:
        project_root: 项目根目录绝对路径
        pattern: 搜索模式（文本或正则）
        file_pattern: 文件名 glob 过滤，默认所有文件
        max_results: 最大返回结果数，默认 50
        use_regex: 是否使用正则表达式，默认为 False（纯文本搜索）
    """
    sandbox = Sandbox(SandboxConfig(root_path=project_root))
    valid, resolved = sandbox.validate_path(".")
    if not valid:
        return json.dumps({"error": resolved}, ensure_ascii=False)

    root = Path(resolved)
    results: list[dict] = []

    try:
        flags = re.MULTILINE | re.IGNORECASE
        if use_regex:
            regex = re.compile(pattern, flags)
        else:
            regex = re.compile(re.escape(pattern), flags)

        for file_path in root.rglob(file_pattern):
            # 跳过 .git, node_modules, __pycache__
            if any(part in {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
                   for part in file_path.parts):
                continue
            if not file_path.is_file():
                continue
            # 只搜文本文件
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for line_no, line in enumerate(content.split("\n"), 1):
                if regex.search(line):
                    rel_path = str(file_path.relative_to(root))
                    results.append({
                        "file": rel_path,
                        "line": line_no,
                        "content": line.strip()[:200],
                    })
                    if len(results) >= max_results:
                        return json.dumps({
                            "pattern": pattern,
                            "results": results,
                            "truncated": True,
                            "total": len(results),
                        }, ensure_ascii=False)

        return json.dumps({
            "pattern": pattern,
            "results": results,
            "truncated": False,
            "total": len(results),
        }, ensure_ascii=False)
    except re.error as e:
        return json.dumps({"error": f"正则表达式错误: {e}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
