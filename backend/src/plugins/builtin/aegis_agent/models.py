"""AegisCode Agent 数据模型。

表名前缀: ``aegis_agent_*``

核心表:
- aegis_agent_runs       Agent 运行实例（一次完整任务）
- aegis_agent_steps      每一步对话/工具调用
- aegis_agent_usage_logs 每次模型调用的精确用量
- aegis_agent_events     结构化事件（span/trace）
- aegis_agent_checkpoints 检查点（暂停/恢复）
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# 运行实例
# ---------------------------------------------------------------------------

class AgentRun(IDMixin, TimestampMixin, Base):
    """一次完整的 Agent 运行（对应一个任务/会话）。

    生命周期: created → running → paused → running → completed/failed/cancelled
    """

    __tablename__ = "aegis_agent_runs"

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="发起用户")
    workspace_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="关联工作区ID"
    )

    # 状态
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="created", index=True,
        comment="created/running/paused/completed/failed/cancelled",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="失败原因")

    # 模型配置
    provider_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="AI Provider ID")
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="模型名")

    # 预算配置
    max_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=200000, comment="最大 Token 预算"
    )
    max_steps: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50, comment="最大步数"
    )
    max_cost_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 6), nullable=True, comment="最大成本(USD)"
    )

    # 实时累计
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_write: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    step_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 工作流
    workflow_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="single",
        comment="single(单角色) / planner_dag(四角色DAG)",
    )
    current_role: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="planner/coder/reviewer/tester"
    )

    # 上下文快照
    context_summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="旧轮压缩摘要（分层上下文的摘要层）"
    )

    def __repr__(self) -> str:
        return f"<AgentRun {self.id} status={self.status}>"


# ---------------------------------------------------------------------------
# 步骤
# ---------------------------------------------------------------------------

class AgentStep(IDMixin, TimestampMixin, Base):
    """Agent 运行中的单步操作。

    每步对应一次 LLM 调用（可能含 tool_calls）或一次工具执行。
    """

    __tablename__ = "aegis_agent_steps"

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aegis_agent_runs.id"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="步骤序号")

    # 步骤类型
    step_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="llm_call / tool_call / tool_result / checkpoint",
    )

    # 角色（多角色工作流时标记）
    role: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="planner/coder/reviewer/tester"
    )

    # LLM 调用内容
    input_messages: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="输入消息(JSON)"
    )
    output_content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="LLM 输出文本"
    )
    tool_calls_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="工具调用列表(JSON)"
    )

    # 工具执行
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tool_args: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="工具参数(JSON)")
    tool_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="工具结果(JSON)")
    tool_success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    tool_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 本步用量
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 循环检测
    result_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="结果哈希（循环检测用）"
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed",
        comment="running/completed/failed/skipped",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AgentStep {self.id} run={self.run_id} idx={self.step_index}>"


# ---------------------------------------------------------------------------
# 精确用量日志
# ---------------------------------------------------------------------------

class AgentUsageLog(IDMixin, TimestampMixin, Base):
    """每次模型调用的精确用量记录。

    对标 OpenCode /usage 与 Gemini CLI 的统计深度。
    所有 token 数值来自 API 返回的 usage 字段，非粗估。
    """

    __tablename__ = "aegis_agent_usage_logs"

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aegis_agent_runs.id"), nullable=False, index=True
    )
    step_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("aegis_agent_steps.id"), nullable=True, index=True
    )

    # 模型维度
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="planner/coder/reviewer/tester"
    )

    # 精确 token（来自 API usage 返回值）
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="思维链 token"
    )
    context_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="本次请求上下文规模"
    )

    # 成本
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))

    # 延迟
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    first_token_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="首 token 延迟")

    # 预算快照
    budget_remaining: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="记录时预算余量(token)"
    )
    budget_usage_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="预算使用百分比"
    )

    def __repr__(self) -> str:
        return f"<AgentUsageLog {self.id} run={self.run_id} model={self.model}>"


# ---------------------------------------------------------------------------
# 结构化事件（Trace）
# ---------------------------------------------------------------------------

class AgentEvent(IDMixin, TimestampMixin, Base):
    """结构化事件——OpenTelemetry 语义的三级 span。

    span 层级: run → step → tool_call
    """

    __tablename__ = "aegis_agent_events"

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aegis_agent_runs.id"), nullable=False, index=True
    )
    step_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("aegis_agent_steps.id"), nullable=True, index=True
    )
    parent_event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("aegis_agent_events.id"), nullable=True, comment="父事件ID"
    )

    # span 信息
    span_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="run / step / tool_call / llm_call",
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="事件名称")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ok",
        comment="ok / error / cancelled",
    )

    # 时间
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now()
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 数据
    attributes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="结构化属性(JSON)"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AgentEvent {self.id} run={self.run_id} type={self.span_type}>"


# ---------------------------------------------------------------------------
# 检查点
# ---------------------------------------------------------------------------

class AgentCheckpoint(IDMixin, TimestampMixin, Base):
    """Agent 运行检查点——支持暂停/恢复。

    检查点包含完整的工作上下文：
    - 消息历史摘要
    - 文件状态指纹
    - 当前步骤位置
    """

    __tablename__ = "aegis_agent_checkpoints"

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aegis_agent_runs.id"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="检查点所在步骤")

    # 上下文快照
    messages_snapshot: Mapped[str] = mapped_column(
        Text, nullable=False, comment="消息历史(JSON)"
    )
    context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_fingerprints: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="文件状态指纹(JSON: {path: hash})"
    )

    # 预算快照
    token_snapshot: Mapped[dict] = mapped_column(
        Text, nullable=False, comment="Token 使用快照(JSON)"
    )

    # 标记
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否为当前活跃检查点"
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="创建原因: auto/manual/pause/budget_warning"
    )

    def __repr__(self) -> str:
        return f"<AgentCheckpoint {self.id} run={self.run_id} step={self.step_index}>"
