"""Todo 工具——Agent 任务清单管理。

设计说明:
- 该工具是纯函数（无状态），返回规范化后的完整 todo 列表 JSON。
- 真正维护 run 级 todo 状态的是 runtime：它调用此工具后，
  解析返回值并同步到 _ActiveRun.todos，再广播 todo_update SSE 事件。
- todo 项数据结构:
  {
    "id": "t1",
    "content": "任务描述",
    "status": "pending" | "in_progress" | "completed" | "cancelled",
    "created_at": "..."
  }
"""

import json
import time
from typing import Any


def _normalize_todo_list(todos: Any) -> list[dict]:
    """规范化入参 todo 列表，过滤非法项。"""
    if not isinstance(todos, list):
        return []
    out: list[dict] = []
    for i, t in enumerate(todos):
        if not isinstance(t, dict):
            continue
        content = str(t.get("content") or "").strip()
        if not content:
            continue
        status = str(t.get("status") or "pending")
        if status not in ("pending", "in_progress", "completed", "cancelled"):
            status = "pending"
        out.append({
            "id": str(t.get("id") or f"t{i + 1}"),
            "content": content,
            "status": status,
        })
    return out


async def aegis_todo_write(
    todos: list[dict],
    action: str = "replace",
) -> str:
    """写入/更新 Agent 任务清单。

    Args:
        todos: 任务清单数组，每项 {id?, content, status?}
              status 取值: pending / in_progress / completed / cancelled
        action: replace=整体替换当前清单（默认），
                append=将新任务追加到现有清单
    """
    normalized = _normalize_todo_list(todos)
    return json.dumps({
        "action": action,
        "todos": normalized,
        "count": len(normalized),
        "note": "任务清单已更新，runtime 会同步到会话",
    }, ensure_ascii=False)


async def aegis_todo_list() -> str:
    """列出当前 Agent 任务清单（由 runtime 注入最新状态）。

    Note: 该工具由 runtime 特殊处理——调用前 runtime 会将当前
    todo 列表作为参数传入，因此 handler 只负责原样返回。
    """
    return json.dumps({
        "todos": [],
        "count": 0,
        "note": "请从运行时上下文读取最新任务清单",
    }, ensure_ascii=False)