"""Agent 预算策略模型。

按 model+user+task_type 维度配置 Agent 运行预算上限。
匹配优先级: model+user+task_type > model+user > model+task_type > model > user+task_type > user > 全局默认
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    pass


class AgentBudgetPolicy(IDMixin, TimestampMixin, Base):
    """Agent 执行预算策略。

    可按 model_name / user_id / task_type 三个维度灵活组合配置。
    所有三个字段均可为 null，表示通配（不限该维度）。
    匹配时按精确度从高到低取第一条 active 策略。
    """

    __tablename__ = "aegis_agent_budget_policies"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="策略名称")
    model_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True, comment="匹配模型名(null=不限)"
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="匹配用户ID(null=不限)"
    )
    task_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True, comment="匹配任务类型(null=不限)"
    )

    # 预算参数
    segment_rounds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=25, comment="分段轮次"
    )
    max_rounds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=75, comment="最大轮次"
    )
    max_tool_calls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=150, comment="最大工具调用次数"
    )
    max_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3600, comment="最大执行时间(秒)"
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=500000, comment="最大 Token 数"
    )
    max_consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, comment="最大连续失败次数"
    )
    max_cost_usd: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="最大成本(USD, 0=不限)"
    )

    # 状态
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True, comment="是否启用"
    )

    def __repr__(self) -> str:
        return f"<AgentBudgetPolicy {self.id} name={self.name} model={self.model_name} user={self.user_id}>"
