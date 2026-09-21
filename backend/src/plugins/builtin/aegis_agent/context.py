"""AegisCode Agent 分层上下文管理。

核心设计（对标调研结论 "压缩是视图不是删除"）:
1. Canonical transcript: 完整消息历史始终保留在内存/DB
2. 三层投影:
   - system 层: 系统提示词（不变）
   - summary 层: 旧轮压缩摘要（超出工作窗口的消息被压缩为摘要）
   - working 层: 近 N 轮原文（保留完整 tool_calls + tool_results）
3. 检索层: 按需从 canonical 中检索相关历史片段（Phase 3 实现 RAG）

参考:
- Cline/Roo: summarization — 旧消息压缩为摘要
- Roo-code: tree-sitter folded file context — 零成本缓解失忆
- OpenHands: 恢复时重建工作区快照
- goose: canonical transcript 保留 + 标记过滤/投影派生
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger


# ---------------------------------------------------------------------------
# 消息类型
# ---------------------------------------------------------------------------

@dataclass
class ContextMessage:
    """上下文中的单条消息。"""
    role: str          # system / user / assistant / tool
    content: str | list = ""  # str 或 OpenAI 多模态 content 数组
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    # 元数据
    tokens_estimated: int = 0
    compressed: bool = False  # 是否已被压缩到摘要层

    def to_llm_dict(self) -> dict[str, Any]:
        """转为 OpenAI 兼容的 messages 格式。"""
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "timestamp": self.timestamp,
            "tokens_estimated": self.tokens_estimated,
            "compressed": self.compressed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ContextMessage":
        return cls(
            role=d["role"],
            content=d.get("content", ""),
            tool_calls=d.get("tool_calls"),
            tool_call_id=d.get("tool_call_id"),
            name=d.get("name"),
            timestamp=d.get("timestamp", datetime.utcnow().isoformat()),
            tokens_estimated=d.get("tokens_estimated", 0),
            compressed=d.get("compressed", False),
        )


# ---------------------------------------------------------------------------
# 分层上下文管理器
# ---------------------------------------------------------------------------

@dataclass
class ContextConfig:
    """上下文管理配置。"""
    working_window: int = 20          # 工作层保留的最近消息数
    max_context_tokens: int = 128_000  # 上下文窗口大小（token）
    summary_trigger_pct: float = 0.75  # 上下文使用达到多少%触发压缩
    min_messages_before_summary: int = 10  # 至少多少条消息才考虑压缩


class LayeredContext:
    """分层上下文管理器。

    三层结构:
    - system 层: 系统提示词
    - summary 层: 旧轮压缩摘要
    - working 层: 近 N 轮原文

    canonical transcript: self._all_messages 保留完整历史
    压缩操作只是将旧消息标记 compressed=True 并生成摘要，
    原始消息**永不删除**（"压缩是视图不是删除"）。
    """

    def __init__(self, config: ContextConfig | None = None):
        self.config = config or ContextConfig()
        self._system_prompt: str = ""
        self._summary: str = ""
        self._all_messages: list[ContextMessage] = []
        self._summary_count: int = 0  # 已压缩过多少轮

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        self._system_prompt = value

    @property
    def summary(self) -> str:
        return self._summary

    @property
    def all_messages(self) -> list[ContextMessage]:
        """完整 canonical transcript（只读视图）。"""
        return list(self._all_messages)

    @property
    def working_messages(self) -> list[ContextMessage]:
        """工作层：未被压缩的最近消息。"""
        return [m for m in self._all_messages if not m.compressed]

    def add_message(self, message: ContextMessage) -> None:
        """添加消息到 canonical transcript。"""
        if not message.tokens_estimated:
            message.tokens_estimated = self._estimate_tokens(message)
        self._all_messages.append(message)

    def add_user_message(self, content: str | list) -> None:
        self.add_message(ContextMessage(role="user", content=content))

    def add_assistant_message(
        self,
        content: str,
        tool_calls: list[dict] | None = None,
    ) -> None:
        self.add_message(ContextMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        ))

    def add_tool_result(
        self,
        tool_call_id: str,
        content: str,
        name: str | None = None,
    ) -> None:
        self.add_message(ContextMessage(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        ))

    def build_llm_messages(self) -> list[dict[str, Any]]:
        """构建发送给 LLM 的 messages 列表。

        结构: [system] + [summary(if exists)] + working_messages
        """
        messages: list[dict[str, Any]] = []

        # system 层
        system_content = self._system_prompt
        if self._summary:
            system_content += f"\n\n## 历史对话摘要\n{self._summary}"
        messages.append({"role": "system", "content": system_content})

        # working 层
        working = self.working_messages
        for m in working:
            messages.append(m.to_llm_dict())

        return messages

    def needs_compression(self) -> bool:
        """判断是否需要触发压缩。"""
        working = self.working_messages
        if len(working) < self.config.min_messages_before_summary:
            return False

        estimated_tokens = self._estimate_total_tokens()
        if estimated_tokens > self.config.max_context_tokens * self.config.summary_trigger_pct:
            return True

        return False

    def compress(self, llm_call: Any | None = None) -> str | None:
        """压缩旧消息到摘要层。

        策略:
        1. 保留最近 working_window 条消息在 working 层
        2. 将超出部分的消息标记 compressed=True
        3. 生成摘要（如果有 LLM 调用函数则用 LLM 摘要，否则用简单截断）

        Args:
            llm_call: 可选的 LLM 摘要函数 (async callable)
                     签名: async def(messages_to_compress: list[dict]) -> str

        Returns:
            摘要文本，或 None（无需压缩）
        """
        working = self.working_messages
        if len(working) <= self.config.working_window:
            return None

        # 分割：保留最后 working_window 条在 working 层
        to_compress = working[:-self.config.working_window]

        # 标记压缩
        for msg in to_compress:
            msg.compressed = True

        self._summary_count += len(to_compress)

        # 生成摘要
        if llm_call:
            # 异步 LLM 摘要（由 runtime 调用时传入）
            return None  # 异步摘要由 runtime 层处理
        else:
            # 简单摘要：拼接关键信息
            summary_parts: list[str] = []
            for msg in to_compress:
                text = msg.content if isinstance(msg.content, str) else "[图片/多模态消息]"
                if msg.role == "user":
                    summary_parts.append(f"用户: {text[:200]}")
                elif msg.role == "assistant":
                    summary_parts.append(f"助手: {text[:200]}")
                elif msg.role == "tool":
                    summary_parts.append(f"工具结果: {text[:100]}")

            new_summary = "\n".join(summary_parts)
            if self._summary:
                self._summary = f"{self._summary}\n\n{new_summary}"
            else:
                self._summary = new_summary

            logger.info(
                f"Context compressed: {len(to_compress)} messages → summary "
                f"(total compressed: {self._summary_count})"
            )
            return self._summary

    def to_snapshot(self) -> str:
        """序列化为 JSON 快照（用于检查点）。"""
        return json.dumps({
            "system_prompt": self._system_prompt,
            "summary": self._summary,
            "summary_count": self._summary_count,
            "messages": [m.to_dict() for m in self._all_messages],
            "config": {
                "working_window": self.config.working_window,
                "max_context_tokens": self.config.max_context_tokens,
                "summary_trigger_pct": self.config.summary_trigger_pct,
                "min_messages_before_summary": self.config.min_messages_before_summary,
            },
        }, ensure_ascii=False)

    @classmethod
    def from_snapshot(cls, snapshot: str) -> "LayeredContext":
        """从 JSON 快照恢复。"""
        data = json.loads(snapshot)
        config = ContextConfig(
            working_window=data["config"]["working_window"],
            max_context_tokens=data["config"]["max_context_tokens"],
            summary_trigger_pct=data["config"]["summary_trigger_pct"],
            min_messages_before_summary=data["config"]["min_messages_before_summary"],
        )
        ctx = cls(config=config)
        ctx._system_prompt = data["system_prompt"]
        ctx._summary = data["summary"]
        ctx._summary_count = data["summary_count"]
        ctx._all_messages = [
            ContextMessage.from_dict(m) for m in data["messages"]
        ]
        return ctx

    # -----------------------------------------------------------------
    # 内部方法
    # -----------------------------------------------------------------

    def _estimate_tokens(self, message: ContextMessage) -> int:
        """粗估单条消息的 token 数。

        仅用于判断是否需要触发压缩，预算控制一律以 API usage 为准。
        """
        content = message.content
        if isinstance(content, list):
            # 多模态 content: 文本部分参与估算，图片按固定 token 粗估
            text = ""
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text += part.get("text", "")
                    elif part.get("type") == "image_url":
                        text += " [image: 1000tokens]"
                elif isinstance(part, str):
                    text += part
        else:
            text = content or ""
        if message.tool_calls:
            text += json.dumps(message.tool_calls, ensure_ascii=False)
        # 粗估: 中文约 1.5 字/token, 英文约 4 字符/token，混合取 ~3
        return max(1, len(text) // 3)

    def _estimate_total_tokens(self) -> int:
        """估算当前构建的 LLM messages 总 token。"""
        total = len(self._system_prompt) // 3
        if self._summary:
            total += len(self._summary) // 3
        for msg in self.working_messages:
            total += msg.tokens_estimated
        return total
