"""安全中心数据模型: API 调用日志、用户操作日志、脱敏规则。

对应旧项目:
- ApiCallLog → 每次 LLM API 调用记录（user/model/tokens/project/ip）
- UserActionLog → 用户关键操作审计（删除项目/文件/成员管理等）
- SanitizeRule → 脱敏规则配置
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin


class ApiCallLog(IDMixin, TimestampMixin, Base):
    """每次 LLM API 调用日志——安全中心 Token 统计的数据源。"""

    __tablename__ = "aegis_api_call_log"

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="用户ID")
    run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="Agent运行ID")
    step_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="步骤ID")
    model: Mapped[str] = mapped_column(String(100), nullable=False, comment="模型名")
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="供应商")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="输入Token数")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="输出Token数")
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="缓存读取Token")
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="缓存写入Token")
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="推理Token")
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="总Token数")
    cost_usd: Mapped[str] = mapped_column(String(20), nullable=False, default="0", comment="费用(USD)")
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="延迟(ms)")
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="请求IP")
    workspace_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="工作区ID")

    def __repr__(self) -> str:
        return f"<ApiCallLog user={self.user_id} model={self.model} total={self.total_tokens}>"


class UserActionLog(IDMixin, TimestampMixin, Base):
    """用户关键操作审计日志。"""

    __tablename__ = "aegis_user_action_log"

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="操作人ID")
    username: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="操作人用户名")
    action: Mapped[str] = mapped_column(String(100), nullable=False, comment="操作类型 e.g. project.delete")
    target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="操作对象类型")
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="操作对象ID")
    target_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="操作对象名称")
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="操作详情(JSON)")
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="请求IP")
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="User-Agent")

    def __repr__(self) -> str:
        return f"<UserActionLog user={self.username} action={self.action}>"


class SanitizeRule(IDMixin, TimestampMixin, Base):
    """脱敏规则——对 Agent 输出/文件内容进行敏感信息脱敏。"""

    __tablename__ = "aegis_sanitize_rule"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="规则名称")
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="规则描述")
    pattern: Mapped[str] = mapped_column(Text, nullable=False, comment="正则表达式")
    replacement: Mapped[str] = mapped_column(String(200), nullable=False, default="***", comment="替换文本")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="优先级(越大越先执行)")
    category: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="分类: phone/email/id_card/api_key/custom"
    )

    def __repr__(self) -> str:
        return f"<SanitizeRule {self.name} enabled={self.enabled}>"
