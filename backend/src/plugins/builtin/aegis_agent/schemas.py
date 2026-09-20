"""AegisCode Agent 请求/响应模型。"""
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------

class RunStatus(str, Enum):
    created = "created"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class WorkflowType(str, Enum):
    single = "single"
    planner_dag = "planner_dag"


class StepType(str, Enum):
    llm_call = "llm_call"
    tool_call = "tool_call"
    tool_result = "tool_result"
    checkpoint = "checkpoint"


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------

class RunCreate(BaseModel):
    """创建 Agent 运行。

    model_config 关闭 pydantic 的 ``model_`` 前缀保护，允许 ``model_name``
    字段名（否则触发 protected namespace 警告）。
    """
    model_config = ConfigDict(protected_namespaces=())

    workspace_id: int | None = Field(default=None, description="关联工作区ID")
    provider_id: int | None = Field(default=None, description="AI Provider ID（留空自动选第一个启用的）")
    model_name: str | None = Field(default=None, description="模型名（留空用 provider 默认）")
    max_tokens: int = Field(default=200000, ge=1000, le=10_000_000, description="Token 预算")
    max_steps: int = Field(default=50, ge=1, le=500, description="最大步数")
    max_cost_usd: Decimal | None = Field(default=None, description="成本上限(USD)")
    workflow_type: WorkflowType = Field(default=WorkflowType.single, description="工作流类型")
    system_prompt: str | None = Field(default=None, description="自定义系统提示词")


class RunMessage(BaseModel):
    """向 Agent 发送消息。"""
    content: str = Field(..., min_length=1, max_length=50000, description="用户消息")
    stream: bool = Field(default=True, description="是否流式返回")


class RunControl(BaseModel):
    """控制 Agent 运行（暂停/恢复/取消）。"""
    action: str = Field(..., pattern="^(pause|resume|cancel)$", description="控制动作")


# ---------------------------------------------------------------------------
# 响应模型
# ---------------------------------------------------------------------------

class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    user_id: int
    workspace_id: int | None = None
    status: str
    model_name: str | None = None
    max_tokens: int
    max_steps: int
    max_cost_usd: Decimal | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read: int = 0
    total_cache_write: int = 0
    total_cost_usd: Decimal = Decimal("0")
    step_count: int = 0
    workflow_type: str = "single"
    current_role: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    step_index: int
    step_type: str
    role: str | None = None
    output_content: str | None = None
    tool_name: str | None = None
    tool_args: str | None = None
    tool_result: str | None = None
    tool_success: bool | None = None
    tool_latency_ms: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    latency_ms: int | None = None
    status: str = "completed"
    error_message: str | None = None
    created_at: datetime


class UsageLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    step_id: int | None = None
    model: str
    provider: str
    role: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    context_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    latency_ms: int | None = None
    first_token_ms: int | None = None
    budget_remaining: int | None = None
    budget_usage_pct: Decimal | None = None
    created_at: datetime


class UsageSummary(BaseModel):
    """用量汇总（按多维度聚合）。"""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read: int = 0
    total_cache_write: int = 0
    total_reasoning_tokens: int = 0
    total_cost_usd: Decimal = Decimal("0")
    call_count: int = 0
    avg_latency_ms: float | None = None


class BudgetStatus(BaseModel):
    """实时预算状态。"""
    max_tokens: int
    used_tokens: int
    remaining_tokens: int
    usage_pct: float
    max_cost_usd: Decimal | None
    total_cost_usd: Decimal
    max_steps: int
    step_count: int
    remaining_steps: int
    warning_level: str = "normal"  # normal / warning / critical / exhausted
