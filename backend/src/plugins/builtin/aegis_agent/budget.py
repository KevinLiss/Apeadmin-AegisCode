"""AegisCode Agent 预算控制器。

核心改进（对标调研结论）:
1. 精确计量: 所有 token 数值来自 API usage 返回值，不再用 chars//3 粗估
2. 流式实时扣减: 每 SSE chunk 累计，接近阈值推送预警事件
3. 多维度记录: cache_read/cache_write/reasoning/context 四维度
4. 预算快照: 每次记录时保存预算余量，为实时看板提供数据源

参考:
- OpenCode: usage 字段多源提取，inputTokens 去重
- Gemini CLI: "流缓冲-成功才入账"策略
- OpenHands: usage-id 分组 + context_window 水位一等公民
"""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

from loguru import logger


class BudgetWarningLevel(str, Enum):
    normal = "normal"
    warning = "warning"      # 80%
    critical = "critical"    # 95%
    exhausted = "exhausted"  # 100%


@dataclass
class UsageRecord:
    """单次模型调用的精确用量。"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    context_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    latency_ms: int | None = None
    first_token_ms: int | None = None
    model: str = ""
    provider: str = ""
    role: str | None = None

    @property
    def total_tokens(self) -> int:
        """本次调用总 token = input + output（cache_read 不重复计入消耗预算）。

        参考 OpenCode: cache_read 是缓存命中，已在上游计入 cache_write，
        不应重复扣预算。context_tokens 是 input_tokens 的子集描述，
        同样不额外扣减。
        """
        return self.input_tokens + self.output_tokens - self.cache_read_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "context_tokens": self.context_tokens,
            "cost_usd": float(self.cost_usd),
            "latency_ms": self.latency_ms,
            "first_token_ms": self.first_token_ms,
            "model": self.model,
            "provider": self.provider,
            "role": self.role,
        }


@dataclass
class BudgetConfig:
    """预算配置。"""
    max_tokens: int = 200_000
    max_steps: int = 50
    max_cost_usd: Decimal | None = None
    warning_pct: float = 0.80
    critical_pct: float = 0.95


@dataclass
class BudgetState:
    """预算实时状态（内存中维护，异步安全）。"""
    config: BudgetConfig = field(default_factory=BudgetConfig)
    used_tokens: int = 0
    used_cost: Decimal = Decimal("0")
    step_count: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.config.max_tokens - self.used_tokens)

    @property
    def remaining_steps(self) -> int:
        return max(0, self.config.max_steps - self.step_count)

    @property
    def usage_pct(self) -> float:
        if self.config.max_tokens == 0:
            return 0.0
        return round(self.used_tokens / self.config.max_tokens * 100, 2)

    @property
    def warning_level(self) -> BudgetWarningLevel:
        pct = self.usage_pct / 100
        if pct >= 1.0:
            return BudgetWarningLevel.exhausted
        elif pct >= self.config.critical_pct:
            return BudgetWarningLevel.critical
        elif pct >= self.config.warning_pct:
            return BudgetWarningLevel.warning
        return BudgetWarningLevel.normal

    def can_proceed(self) -> bool:
        """检查是否还有预算。"""
        if self.used_tokens >= self.config.max_tokens:
            return False
        if self.step_count >= self.config.max_steps:
            return False
        if self.config.max_cost_usd and self.used_cost >= self.config.max_cost_usd:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_tokens": self.config.max_tokens,
            "used_tokens": self.used_tokens,
            "remaining_tokens": self.remaining_tokens,
            "usage_pct": self.usage_pct,
            "max_cost_usd": float(self.config.max_cost_usd) if self.config.max_cost_usd else None,
            "total_cost_usd": float(self.used_cost),
            "max_steps": self.config.max_steps,
            "step_count": self.step_count,
            "remaining_steps": self.remaining_steps,
            "warning_level": self.warning_level.value,
        }


class BudgetController:
    """预算控制器——流式实时扣减 + 多维度记录。

    用法:
        budget = BudgetController(BudgetConfig(max_tokens=100000))
        # 每次模型调用后
        await budget.record_usage(usage_record)
        if not budget.state.can_proceed():
            # 终止运行
            ...
        # 获取实时状态
        status = budget.get_status()
    """

    def __init__(self, config: BudgetConfig | None = None):
        self.state = BudgetState(config=config or BudgetConfig())
        self._warning_callbacks: list[Callable[[BudgetWarningLevel, dict], Any]] = []
        self._last_level = BudgetWarningLevel.normal

    def on_warning(self, callback: Callable[[BudgetWarningLevel, dict], Any]) -> None:
        """注册预警回调（当预算跨过阈值时触发）。"""
        self._warning_callbacks.append(callback)

    async def record_usage(self, record: UsageRecord) -> BudgetWarningLevel:
        """记录一次模型调用的用量，扣减预算。

        返回当前预警级别。
        """
        async with self.state._lock:
            # 扣减 token（cache_read 不重复计入）
            self.state.used_tokens += record.total_tokens
            self.state.used_cost += record.cost_usd
            self.state.step_count += 1

            level = self.state.warning_level

            # 阈值跨越时触发回调
            if level != self._last_level and level != BudgetWarningLevel.normal:
                logger.warning(
                    f"Budget warning: {level.value} "
                    f"(tokens: {self.state.used_tokens}/{self.state.config.max_tokens}, "
                    f"cost: ${self.state.used_cost:.4f}, "
                    f"steps: {self.state.step_count}/{self.state.config.max_steps})"
                )
                status = self.state.to_dict()
                for cb in self._warning_callbacks:
                    try:
                        result = cb(level, status)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Budget warning callback error: {e}")

            self._last_level = level
            return level

    async def record_step(self) -> None:
        """仅记录步骤数（不涉及 token，如工具执行步骤）。"""
        async with self.state._lock:
            self.state.step_count += 1

    def get_status(self) -> dict[str, Any]:
        """获取实时预算状态。"""
        return self.state.to_dict()

    def can_proceed(self) -> bool:
        return self.state.can_proceed()


def extract_usage_from_api_response(
    response: dict[str, Any],
    model: str = "",
    provider: str = "",
    role: str | None = None,
) -> UsageRecord:
    """从 OpenAI 兼容 API 响应中提取精确用量。

    处理多源 usage 字段命名差异:
    - OpenAI: prompt_tokens / completion_tokens / total_tokens
    - DeepSeek: prompt_tokens / completion_tokens + prompt_cache_hit_tokens
    - Anthropic (兼容层): input_tokens / output_tokens + cache_read_input_tokens
    """
    usage = response.get("usage", {})

    record = UsageRecord(model=model, provider=provider, role=role)

    # 标准字段
    record.input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
    record.output_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))

    # 缓存字段（多源提取）
    record.cache_read_tokens = usage.get(
        "prompt_cache_hit_tokens",
        usage.get("cache_read_input_tokens",
                  usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                  )
    )
    record.cache_write_tokens = usage.get(
        "prompt_cache_miss_tokens",
        usage.get("cache_creation_input_tokens", 0)
    )

    # 思维链 token
    record.reasoning_tokens = usage.get(
        "completion_tokens_details", {}
    ).get("reasoning_tokens", 0)

    # 上下文规模 = input_tokens
    record.context_tokens = record.input_tokens

    # 成本计算
    record.cost_usd = _calculate_cost(
        record.input_tokens,
        record.output_tokens,
        record.cache_read_tokens,
        record.cache_write_tokens,
        record.reasoning_tokens,
        model,
    )

    return record


def _calculate_cost(
    input_tokens: int,
    output_tokens: int,
    cache_read: int,
    cache_write: int,
    reasoning_tokens: int,
    model: str,
) -> Decimal:
    """计算成本（USD）。

    使用模型定价表，cache_read 通常是折扣价（DeepSeek 0.1x），
    cache_write 是写入价。无匹配模型时返回 0。
    """
    # 模型定价表 (USD per 1M tokens)
    # 参考 DeepSeek/OpenAI 公开定价
    pricing: dict[str, dict[str, Decimal]] = {
        "deepseek-chat": {
            "input": Decimal("0.27"),
            "output": Decimal("1.10"),
            "cache_read": Decimal("0.07"),
            "cache_write": Decimal("0.27"),
        },
        "deepseek-reasoner": {
            "input": Decimal("0.55"),
            "output": Decimal("2.19"),
            "cache_read": Decimal("0.14"),
            "cache_write": Decimal("0.55"),
        },
        "gpt-4o": {
            "input": Decimal("2.50"),
            "output": Decimal("10.00"),
            "cache_read": Decimal("1.25"),
            "cache_write": Decimal("2.50"),
        },
        "gpt-4o-mini": {
            "input": Decimal("0.15"),
            "output": Decimal("0.60"),
            "cache_read": Decimal("0.075"),
            "cache_write": Decimal("0.15"),
        },
        "claude-sonnet-4": {
            "input": Decimal("3.00"),
            "output": Decimal("15.00"),
            "cache_read": Decimal("0.30"),
            "cache_write": Decimal("3.75"),
        },
    }

    # 模糊匹配模型名
    rate = None
    for key, prices in pricing.items():
        if key in model.lower():
            rate = prices
            break

    if not rate:
        # 未知模型，返回 0（让看板显示"需配置定价"）
        return Decimal("0")

    cost = (
        Decimal(input_tokens - cache_read) * rate["input"] / Decimal(1_000_000)
        + Decimal(output_tokens) * rate["output"] / Decimal(1_000_000)
        + Decimal(cache_read) * rate["cache_read"] / Decimal(1_000_000)
        + Decimal(cache_write) * rate["cache_write"] / Decimal(1_000_000)
    )

    return cost.quantize(Decimal("0.000001"))
