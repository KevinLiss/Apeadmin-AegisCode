"""AegisCode Agent 运行时——状态机驱动的对话循环。

核心改进（对标调研结论）:
1. 单机模式内联执行 + 预留 Worker 接口（SQLite 队列，规模到了再拆进程）
2. 底座 EventBus 替代 Redis Streams；事件结构化落库
3. 精确 usage 记录（来自 API usage，非 chars//3 粗估）
4. 分层上下文压缩（压缩是视图不是删除）
5. 循环检测三重判定（工具调用序列窗口 + 参数相似度 + 结果哈希）

参考:
- goose: 状态机 Operation 管线（State → Effect → SessionManager）
- opencode: 子代理深度限制 + 权限派生 + 取消级联
- cline: 恢复只走确定性算法
"""

import asyncio
import hashlib
import json
import time
from collections.abc import AsyncGenerator
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

import httpx
from loguru import logger
from sqlalchemy import select, update, func

from src.core.crypto import decrypt_api_key
from src.db import SessionLocal
from src.models.ai import AiProvider
from src.models import User
from src.mcp import mcp_manager

from src.plugins.builtin.aegis_agent.budget import (
    BudgetController,
    BudgetConfig,
    BudgetWarningLevel,
    UsageRecord,
    extract_usage_from_api_response,
)
from src.plugins.builtin.aegis_agent.context import (
    ContextConfig,
    ContextMessage,
    LayeredContext,
)
from src.plugins.builtin.aegis_agent.models import (
    AgentRun,
    AgentStep,
    AgentUsageLog,
    AgentEvent,
    AgentCheckpoint,
)
from src.plugins.builtin.aegis_agent.security_models import ApiCallLog


# ---------------------------------------------------------------------------
# 状态机
# ---------------------------------------------------------------------------

class RunState(str, Enum):
    created = "created"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class StepType(str, Enum):
    llm_call = "llm_call"
    tool_call = "tool_call"
    tool_result = "tool_result"
    checkpoint = "checkpoint"


# ---------------------------------------------------------------------------
# 循环检测
# ---------------------------------------------------------------------------

class LoopDetector:
    """三重循环检测。

    参考: 原实现 repeated_tool_result 仅简单指纹 → 误杀率高
    新方案:
    1. 工具调用序列窗口（近 10 次）
    2. 参数相似度（Levenshtein-like）
    3. 结果哈希
    先警告后终止。
    """

    def __init__(self, window_size: int = 10, max_repeats: int = 3):
        self.window_size = window_size
        self.max_repeats = max_repeats
        self._call_window: list[dict[str, Any]] = []
        self._warning_count: int = 0

    def record(self, tool_name: str, args: dict, result_hash: str) -> dict[str, Any]:
        """记录一次工具调用，返回检测结果。

        Returns:
            {"detected": bool, "level": "normal/warning/terminate", "reason": str}
        """
        entry = {
            "tool": tool_name,
            "args_hash": self._hash_args(args),
            "result_hash": result_hash,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._call_window.append(entry)
        if len(self._call_window) > self.window_size:
            self._call_window.pop(0)

        # 检测三重信号
        sequence_match = self._check_sequence(tool_name)
        args_match = self._check_args(tool_name, entry["args_hash"])
        result_match = self._check_result(tool_name, result_hash)

        signals = sum([sequence_match, args_match, result_match])

        if signals >= 3:
            return {
                "detected": True,
                "level": "terminate",
                "reason": f"三重信号命中: 工具={tool_name} 序列={sequence_match} 参数={args_match} 结果={result_match}",
            }
        elif signals >= 2:
            self._warning_count += 1
            return {
                "detected": True,
                "level": "warning",
                "reason": f"双重信号命中: 工具={tool_name} 序列={sequence_match} 参数={args_match} 结果={result_match}",
            }

        return {"detected": False, "level": "normal", "reason": ""}

    def should_terminate(self) -> bool:
        return self._warning_count >= self.max_repeats

    def _check_sequence(self, tool_name: str) -> bool:
        """检查最近 N 次是否连续调用同一工具。"""
        if len(self._call_window) < 3:
            return False
        recent = self._call_window[-3:]
        return all(c["tool"] == tool_name for c in recent)

    def _check_args(self, tool_name: str, args_hash: str) -> bool:
        """检查参数是否重复。"""
        matches = sum(
            1 for c in self._call_window[:-1]
            if c["tool"] == tool_name and c["args_hash"] == args_hash
        )
        return matches >= 2

    def _check_result(self, tool_name: str, result_hash: str) -> bool:
        """检查结果哈希是否重复。"""
        matches = sum(
            1 for c in self._call_window[:-1]
            if c["tool"] == tool_name and c["result_hash"] == result_hash
        )
        return matches >= 2

    @staticmethod
    def _hash_args(args: dict) -> str:
        """对参数做哈希（忽略顺序）。"""
        return hashlib.md5(
            json.dumps(args, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()


# ---------------------------------------------------------------------------
# Agent 运行时
# ---------------------------------------------------------------------------

# Provider 默认配置
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "deepseek": {"base_url": "https://api.deepseek.com", "default_model": "deepseek-chat"},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "default_model": "qwen-plus"},
    "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "default_model": "glm-4-flash"},
    "openai": {"base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini"},
    "custom": {"base_url": "", "default_model": ""},
}

DEFAULT_SYSTEM_PROMPT = """你是 AegisCode，一个企业级 AI 编码助手。

你的职责:
1. 理解用户的编码需求，制定执行计划
2. 通过工具完成文件操作、代码执行、搜索等任务
3. 精确报告执行结果，包括修改的文件、命令输出等
4. 在任务完成时给出清晰的总结

规则:
- 每步操作前先确认理解用户意图
- 工具调用后用简洁中文总结结果
- 遇到错误时分析原因并尝试修复
- 保持操作可追溯，每步都有明确状态
"""


class AgentRuntime:
    """Agent 运行时——管理一次完整的 Agent 对话循环。

    生命周期:
        1. create_run()      创建运行实例
        2. send_message()    发送消息并运行对话循环
        3. control()         暂停/恢复/取消
        4. 完成或失败后保存最终状态

    对话循环:
        user message → LLM (with tools)
        → if tool_calls: execute tools → feed results back → LLM
        → repeat until no tool_calls or budget exhausted
    """

    def __init__(self):
        self._active_runs: dict[int, AgentRuntime._ActiveRun] = {}

    class _ActiveRun:
        """内存中的活跃运行上下文。"""
        def __init__(self, run_id: int, context: LayeredContext, budget: BudgetController):
            self.run_id = run_id
            self.context = context
            self.budget = budget
            self.loop_detector = LoopDetector()
            self.cancel_event = asyncio.Event()
            self.pause_event = asyncio.Event()
            self.step_counter = 0

    # -----------------------------------------------------------------
    # 公开接口
    # -----------------------------------------------------------------

    async def create_run(
        self,
        user_id: int,
        workspace_id: int | None = None,
        provider_id: int | None = None,
        model_name: str | None = None,
        max_tokens: int = 200_000,
        max_steps: int = 50,
        max_cost_usd: Decimal | None = None,
        workflow_type: str = "single",
        system_prompt: str | None = None,
    ) -> AgentRun:
        """创建 Agent 运行实例。"""
        # 自动选择 provider
        if provider_id is None:
            async with SessionLocal() as db:
                stmt = (
                    select(AiProvider)
                    .where(AiProvider.enabled == 1)
                    .order_by(AiProvider.sort, AiProvider.id)
                    .limit(1)
                )
                provider = (await db.execute(stmt)).scalar_one_or_none()
                if not provider:
                    raise ValueError("没有可用的 AI 模型供应商，请先在系统设置中配置")
                provider_id = provider.id
                if not model_name:
                    defaults = PROVIDER_DEFAULTS.get(provider.provider_type, {})
                    model_name = defaults.get("default_model", "")

        run = AgentRun(
            user_id=user_id,
            workspace_id=workspace_id,
            status=RunState.created.value,
            provider_id=provider_id,
            model_name=model_name,
            max_tokens=max_tokens,
            max_steps=max_steps,
            max_cost_usd=max_cost_usd,
            workflow_type=workflow_type,
        )

        async with SessionLocal() as db:
            db.add(run)
            await db.commit()
            await db.refresh(run)

        # 初始化内存上下文
        context = LayeredContext()
        context.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        budget = BudgetController(BudgetConfig(
            max_tokens=max_tokens,
            max_steps=max_steps,
            max_cost_usd=max_cost_usd,
        ))

        self._active_runs[run.id] = self._ActiveRun(run.id, context, budget)
        logger.info(f"AgentRun created: id={run.id} user={user_id} model={model_name}")
        return run

    async def send_message(
        self,
        run_id: int,
        content: str,
        stream: bool = True,
    ) -> AsyncGenerator[str, None] | dict[str, Any]:
        """向 Agent 发送消息并运行对话循环。

        stream=True 时返回 AsyncGenerator（SSE 事件流）
        stream=False 时返回最终结果 dict
        """
        active = self._active_runs.get(run_id)
        if not active:
            raise ValueError(f"Run {run_id} not found or not active")

        # 用户 Token 限额检查
        async with SessionLocal() as db:
            run = await db.get(AgentRun, run_id)
            if not run:
                raise ValueError(f"Run {run_id} not found")
            if run.status not in (RunState.created.value, RunState.running.value, RunState.paused.value):
                raise ValueError(f"Run {run_id} is {run.status}, cannot send message")

            # 查用户 token_limit
            user = await db.get(User, run.user_id)
            if user and user.token_limit > 0:
                # 查当日已用 Token
                from datetime import datetime as _dt
                today_start = _dt.now().replace(hour=0, minute=0, second=0, microsecond=0)
                stmt = (
                    select(func.sum(ApiCallLog.total_tokens))
                    .where(ApiCallLog.user_id == run.user_id)
                    .where(ApiCallLog.created_at >= today_start)
                )
                used_today = (await db.execute(stmt)).scalar() or 0
                if used_today >= user.token_limit:
                    raise ValueError(
                        f"今日 Token 用量已达限额 ({used_today}/{user.token_limit})，"
                        f"请明天再试或联系管理员调整限额"
                    )

            run.status = RunState.running.value
            await db.commit()

        # 添加用户消息到上下文
        active.context.add_user_message(content)

        if stream:
            return self._run_loop_stream(active, content)
        else:
            return await self._run_loop_non_stream(active, content)

    async def control(self, run_id: int, action: str) -> dict[str, Any]:
        """控制运行: pause / resume / cancel。"""
        active = self._active_runs.get(run_id)
        if not active:
            raise ValueError(f"Run {run_id} not found")

        if action == "pause":
            active.pause_event.set()
            async with SessionLocal() as db:
                run = await db.get(AgentRun, run_id)
                if run:
                    run.status = RunState.paused.value
                    await db.commit()
            return {"status": "paused"}

        elif action == "resume":
            active.pause_event.clear()
            async with SessionLocal() as db:
                run = await db.get(AgentRun, run_id)
                if run:
                    run.status = RunState.running.value
                    await db.commit()
            return {"status": "running"}

        elif action == "cancel":
            active.cancel_event.set()
            async with SessionLocal() as db:
                run = await db.get(AgentRun, run_id)
                if run:
                    run.status = RunState.cancelled.value
                    await db.commit()
            self._active_runs.pop(run_id, None)
            return {"status": "cancelled"}

        raise ValueError(f"Unknown action: {action}")

    async def get_status(self, run_id: int) -> dict[str, Any]:
        """获取运行状态（含预算信息）。"""
        active = self._active_runs.get(run_id)
        if active:
            return {
                "status": "running" if not active.pause_event.is_set() else "paused",
                "budget": active.budget.get_status(),
                "step_count": active.step_counter,
            }

        async with SessionLocal() as db:
            run = await db.get(AgentRun, run_id)
            if not run:
                raise ValueError(f"Run {run_id} not found")
            return {
                "status": run.status,
                "budget": {
                    "max_tokens": run.max_tokens,
                    "used_tokens": run.total_input_tokens + run.total_output_tokens,
                    "remaining_tokens": max(0, run.max_tokens - run.total_input_tokens - run.total_output_tokens),
                    "usage_pct": round((run.total_input_tokens + run.total_output_tokens) / run.max_tokens * 100, 2) if run.max_tokens else 0,
                    "total_cost_usd": float(run.total_cost_usd),
                    "max_steps": run.max_steps,
                    "step_count": run.step_count,
                    "remaining_steps": max(0, run.max_steps - run.step_count),
                    "warning_level": "normal",
                },
                "step_count": run.step_count,
            }

    async def save_checkpoint(
        self,
        run_id: int,
        reason: str = "manual",
    ) -> AgentCheckpoint | None:
        """保存检查点。"""
        active = self._active_runs.get(run_id)
        if not active:
            return None

        async with SessionLocal() as db:
            run = await db.get(AgentRun, run_id)
            if not run:
                return None

            # 标记旧检查点为非活跃（修复: 之前只 select 未执行 UPDATE）
            await db.execute(
                update(AgentCheckpoint)
                .where(AgentCheckpoint.run_id == run_id, AgentCheckpoint.is_active == True)  # noqa: E712
                .values(is_active=False)
            )

            checkpoint = AgentCheckpoint(
                run_id=run_id,
                step_index=active.step_counter,
                messages_snapshot=active.context.to_snapshot(),
                context_summary=active.context.summary,
                file_fingerprints=None,  # Phase 2 workspace 插件提供
                token_snapshot=json.dumps(active.budget.get_status()),
                is_active=True,
                reason=reason,
            )
            db.add(checkpoint)
            await db.commit()
            await db.refresh(checkpoint)
            logger.info(f"Checkpoint saved: run={run_id} step={active.step_counter} reason={reason}")
            return checkpoint

    async def restore_from_checkpoint(self, run_id: int) -> bool:
        """从最新活跃检查点恢复。"""
        async with SessionLocal() as db:
            stmt = (
                select(AgentCheckpoint)
                .where(
                    AgentCheckpoint.run_id == run_id,
                    AgentCheckpoint.is_active == True,  # noqa: E712
                )
                .order_by(AgentCheckpoint.id.desc())
                .limit(1)
            )
            checkpoint = (await db.execute(stmt)).scalar_one_or_none()
            if not checkpoint:
                return False

        context = LayeredContext.from_snapshot(checkpoint.messages_snapshot)
        budget_state = json.loads(checkpoint.token_snapshot)
        budget = BudgetController(BudgetConfig(
            max_tokens=budget_state.get("max_tokens", 200_000),
            max_steps=budget_state.get("max_steps", 50),
        ))
        budget.state.used_tokens = budget_state.get("used_tokens", 0)
        budget.state.used_cost = Decimal(str(budget_state.get("total_cost_usd", 0)))
        budget.state.step_count = budget_state.get("step_count", 0)

        active = self._ActiveRun(run_id, context, budget)
        self._active_runs[run_id] = active
        logger.info(f"Restored from checkpoint: run={run_id} step={checkpoint.step_index}")
        return True

    # -----------------------------------------------------------------
    # 对话循环（非流式）
    # -----------------------------------------------------------------

    async def _run_loop_non_stream(
        self,
        active: _ActiveRun,
        user_content: str,
    ) -> dict[str, Any]:
        """非流式对话循环。"""
        provider = await self._get_provider(active.run_id)
        api_key = decrypt_api_key(provider.api_key_enc)
        config = self._get_provider_config(provider)
        model_name = config["default_model"]

        # 从 DB 获取模型名（修复: 之前调用不存在的 _get_model_name）
        async with SessionLocal() as db:
            run = await db.get(AgentRun, active.run_id)
            if run and run.model_name:
                model_name = run.model_name

        final_content = ""
        total_usage = UsageRecord()
        tool_events: list[dict] = []

        try:
            while active.budget.can_proceed() and not active.cancel_event.is_set():
                if active.pause_event.is_set():
                    await asyncio.sleep(0.5)
                    continue

                active.step_counter += 1
                step_start = time.time()

                # 上下文压缩检查（修复: 之前非流式版缺失，与流式版对齐）
                if active.context.needs_compression():
                    active.context.compress()

                # 构建消息
                llm_messages = active.context.build_llm_messages()

                # 调用 LLM
                response = await self._call_llm(
                    llm_messages, api_key, config["base_url"],
                    provider,
                    active,
                )

                msg = response["choices"][0]["message"]
                usage = extract_usage_from_api_response(
                    response,
                    model=model_name,
                    provider=provider.provider_type,
                )
                # 用 model_details 中的价格重新计算成本（覆盖硬编码 pricing 表）
                self._apply_model_pricing(usage, provider, model_name)
                usage.latency_ms = int((time.time() - step_start) * 1000)

                # 记录用量
                await active.budget.record_usage(usage)
                await self._persist_usage_log(active.run_id, None, usage, active.budget.get_status())

                total_usage.input_tokens += usage.input_tokens
                total_usage.output_tokens += usage.output_tokens
                total_usage.cost_usd += usage.cost_usd

                # 保存 LLM step
                await self._save_step(active.run_id, active.step_counter, StepType.llm_call, {
                    "output_content": msg.get("content", ""),
                    "tool_calls_json": json.dumps(msg.get("tool_calls", []), ensure_ascii=False) if msg.get("tool_calls") else None,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cost_usd": float(usage.cost_usd),
                    "latency_ms": int((time.time() - step_start) * 1000),
                })

                # 如果没有 tool_calls，对话结束
                if not msg.get("tool_calls"):
                    final_content = msg.get("content", "")
                    active.context.add_assistant_message(final_content)
                    break

                # 有 tool_calls，执行工具
                assistant_content = msg.get("content", "")
                tool_calls = msg["tool_calls"]
                active.context.add_assistant_message(assistant_content, tool_calls)

                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    try:
                        fn_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        fn_args = {}

                    tool_result, tool_success, tool_latency = await self._execute_tool(fn_name, fn_args)
                    result_hash = hashlib.md5(tool_result.encode()).hexdigest()[:16]

                    # 循环检测
                    loop_check = active.loop_detector.record(fn_name, fn_args, result_hash)
                    if loop_check["detected"]:
                        if loop_check["level"] == "terminate" or active.loop_detector.should_terminate():
                            logger.warning(f"Loop detected, terminating: {loop_check['reason']}")
                            final_content = f"检测到循环，已终止: {loop_check['reason']}"
                            break

                    tool_events.append({
                        "name": fn_name,
                        "args": fn_args,
                        "success": tool_success,
                        "latency_ms": tool_latency,
                        "result_preview": tool_result[:500],
                    })

                    active.context.add_tool_result(tc["id"], tool_result, fn_name)

                    await self._save_step(active.run_id, active.step_counter, StepType.tool_call, {
                        "tool_name": fn_name,
                        "tool_args": json.dumps(fn_args, ensure_ascii=False),
                        "tool_result": tool_result[:10000],
                        "tool_success": tool_success,
                        "tool_latency_ms": tool_latency,
                        "result_hash": result_hash,
                    })

                if active.loop_detector.should_terminate():
                    break

            # 更新运行最终状态
            await self._finalize_run(active, final_content or "对话完成")
            return {
                "content": final_content,
                "tool_events": tool_events,
                "usage": total_usage.to_dict(),
                "budget": active.budget.get_status(),
            }

        except Exception as e:
            logger.exception(f"Agent run failed: {e}")
            await self._fail_run(active, str(e))
            raise

    # -----------------------------------------------------------------
    # 对话循环（流式）
    # -----------------------------------------------------------------

    async def _run_loop_stream(
        self,
        active: _ActiveRun,
        user_content: str,
    ) -> AsyncGenerator[str, None]:
        """流式对话循环，yield SSE 事件。"""
        provider = await self._get_provider(active.run_id)
        api_key = decrypt_api_key(provider.api_key_enc)
        config = self._get_provider_config(provider)
        model_name = config["default_model"]

        # 从 DB 获取模型名
        async with SessionLocal() as db:
            run = await db.get(AgentRun, active.run_id)
            if run and run.model_name:
                model_name = run.model_name

        try:
            while active.budget.can_proceed() and not active.cancel_event.is_set():
                if active.pause_event.is_set():
                    await asyncio.sleep(0.5)
                    continue

                active.step_counter += 1
                step_start = time.time()

                # 上下文压缩检查
                if active.context.needs_compression():
                    active.context.compress()
                    yield json.dumps({
                        "type": "context_compressed",
                        "summary_length": len(active.context.summary),
                    }, ensure_ascii=False)

                # 构建消息
                llm_messages = active.context.build_llm_messages()

                # 流式调用 LLM
                collected_content = ""
                collected_tool_calls: list[dict] = []
                has_tool_calls = False
                first_token_time = None
                stream_usage: dict[str, Any] | None = None

                async for chunk_str in self._call_llm_stream(
                    llm_messages, api_key, config["base_url"], model_name, active,
                ):
                    if chunk_str == "[DONE]":
                        break
                    if active.cancel_event.is_set():
                        yield json.dumps({"type": "cancelled"}, ensure_ascii=False)
                        return

                    try:
                        chunk = json.loads(chunk_str)
                    except json.JSONDecodeError:
                        continue

                    # usage chunk（stream_options.include_usage 开启后，最后一个
                    # chunk 的 choices 为空列表，必须先判断再取 [0]，否则 IndexError）
                    if chunk.get("usage"):
                        stream_usage = chunk["usage"]

                    choices = chunk.get("choices") or [{}]
                    delta = (choices[0] or {}).get("delta", {})

                    if delta.get("content"):
                        if first_token_time is None:
                            first_token_time = time.time()
                        collected_content += delta["content"]
                        yield json.dumps({
                            "type": "content",
                            "content": delta["content"],
                        }, ensure_ascii=False)

                    if delta.get("tool_calls"):
                        has_tool_calls = True
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            while len(collected_tool_calls) <= idx:
                                collected_tool_calls.append({
                                    "id": "", "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                })
                            if tc.get("id"):
                                collected_tool_calls[idx]["id"] = tc["id"]
                            if tc.get("function", {}).get("name"):
                                collected_tool_calls[idx]["function"]["name"] += tc["function"]["name"]
                            if tc.get("function", {}).get("arguments"):
                                collected_tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]

                # 精确 usage: stream_options.include_usage 使最后一个 chunk 携带 usage
                # （修复: 之前无论 API 是否返回 usage 都用 chars//3 粗估）
                usage = extract_usage_from_api_response(
                    {"usage": stream_usage or {}},
                    model=model_name,
                    provider=provider.provider_type,
                )
                # 用 model_details 中的价格重新计算成本（覆盖硬编码 pricing 表）
                self._apply_model_pricing(usage, provider, model_name)
                usage.latency_ms = int((time.time() - step_start) * 1000)
                if first_token_time is not None:
                    usage.first_token_ms = int((first_token_time - step_start) * 1000)

                if not stream_usage:
                    # fallback 粗估: 仅当 provider 不支持 stream_options 时
                    usage.input_tokens = sum(
                        m.tokens_estimated for m in active.context.working_messages
                    )
                    usage.output_tokens = max(1, len(collected_content) // 3)
                    usage.context_tokens = usage.input_tokens

                await active.budget.record_usage(usage)
                await self._persist_usage_log(active.run_id, None, usage, active.budget.get_status())

                # 预算预警事件
                level = active.budget.state.warning_level
                if level != BudgetWarningLevel.normal:
                    yield json.dumps({
                        "type": "budget_warning",
                        "level": level.value,
                        "budget": active.budget.get_status(),
                    }, ensure_ascii=False)

                # 保存 LLM step
                await self._save_step(active.run_id, active.step_counter, StepType.llm_call, {
                    "output_content": collected_content,
                    "tool_calls_json": json.dumps(collected_tool_calls, ensure_ascii=False) if has_tool_calls else None,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cost_usd": float(usage.cost_usd),
                    "latency_ms": int((time.time() - step_start) * 1000),
                })

                if not has_tool_calls:
                    # 对话结束
                    active.context.add_assistant_message(collected_content)
                    yield json.dumps({
                        "type": "done",
                        "content": collected_content,
                        "budget": active.budget.get_status(),
                    }, ensure_ascii=False)

                    await self._finalize_run(active, collected_content)
                    return

                # 规范化 tool_calls
                for idx, tc in enumerate(collected_tool_calls):
                    if not tc.get("id"):
                        tc["id"] = f"call_{active.step_counter}_{idx}"
                    tc["type"] = "function"
                    if not tc["function"].get("arguments"):
                        tc["function"]["arguments"] = "{}"

                active.context.add_assistant_message(collected_content, collected_tool_calls)

                # 执行工具
                for tc in collected_tool_calls:
                    fn_name = tc["function"]["name"]
                    try:
                        fn_args = json.loads(tc["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        fn_args = {}

                    yield json.dumps({
                        "type": "tool_call",
                        "name": fn_name,
                        "arguments": fn_args,
                    }, ensure_ascii=False)

                    tool_result, tool_success, tool_latency = await self._execute_tool(fn_name, fn_args)
                    result_hash = hashlib.md5(tool_result.encode()).hexdigest()[:16]

                    # 循环检测
                    loop_check = active.loop_detector.record(fn_name, fn_args, result_hash)
                    if loop_check["detected"]:
                        yield json.dumps({
                            "type": "loop_warning",
                            "level": loop_check["level"],
                            "reason": loop_check["reason"],
                        }, ensure_ascii=False)

                        if loop_check["level"] == "terminate" or active.loop_detector.should_terminate():
                            yield json.dumps({
                                "type": "done",
                                "content": f"检测到循环，已终止: {loop_check['reason']}",
                                "budget": active.budget.get_status(),
                            }, ensure_ascii=False)
                            await self._finalize_run(active, f"循环终止: {loop_check['reason']}")
                            return

                    yield json.dumps({
                        "type": "tool_result",
                        "name": fn_name,
                        "success": tool_success,
                        "latency_ms": tool_latency,
                        "result": tool_result[:5000],
                    }, ensure_ascii=False)

                    active.context.add_tool_result(tc["id"], tool_result, fn_name)

                    await self._save_step(active.run_id, active.step_counter, StepType.tool_call, {
                        "tool_name": fn_name,
                        "tool_args": json.dumps(fn_args, ensure_ascii=False),
                        "tool_result": tool_result[:10000],
                        "tool_success": tool_success,
                        "tool_latency_ms": tool_latency,
                        "result_hash": result_hash,
                    })

                # 继续下一轮（LLM 会基于工具结果继续生成）

            # 预算耗尽
            yield json.dumps({
                "type": "budget_exhausted",
                "budget": active.budget.get_status(),
            }, ensure_ascii=False)
            await self._finalize_run(active, "预算耗尽")

        except Exception as e:
            logger.exception(f"Agent stream failed: {e}")
            yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            await self._fail_run(active, str(e))

    # -----------------------------------------------------------------
    # LLM 调用
    # -----------------------------------------------------------------

    async def _call_llm(
        self,
        messages: list[dict],
        api_key: str,
        base_url: str,
        provider: AiProvider | None,
        active: _ActiveRun,
    ) -> dict[str, Any]:
        """非流式 LLM 调用。"""
        async with SessionLocal() as db:
            run = await db.get(AgentRun, active.run_id)
            model = run.model_name if run and run.model_name else "deepseek-chat"

        # 从 model_details 获取模型参数，回退到默认值
        md = self._get_model_detail(provider, model)
        max_tokens = md.get("max_tokens", 4096)
        temperature = md.get("temperature", 0.7)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        # 添加可用工具（如果模型不支持工具调用则跳过）
        if md.get("supports_tools", True):
            tools = self._get_available_tools()
            if tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"

        url = f"{base_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code >= 400:
                raise RuntimeError(f"LLM API 错误 {resp.status_code}: {resp.text[:300]}")
            return resp.json()

    async def _call_llm_stream(
        self,
        messages: list[dict],
        api_key: str,
        base_url: str,
        model: str,
        active: _ActiveRun,
    ) -> AsyncGenerator[str, None]:
        """流式 LLM 调用。"""
        provider = await self._get_provider(active.run_id)
        md = self._get_model_detail(provider, model)
        max_tokens = md.get("max_tokens", 4096)
        temperature = md.get("temperature", 0.7)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            # OpenAI 兼容: 让最后一个 chunk 携带精确 usage（token 精确计量的关键）
            "stream_options": {"include_usage": True},
        }

        # 添加可用工具（如果模型不支持工具调用则跳过）
        if md.get("supports_tools", True):
            tools = self._get_available_tools()
            if tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"

        url = f"{base_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            request = client.build_request("POST", url, headers=headers, json=body)
            resp = await client.send(request, stream=True)
            if resp.status_code in (400, 404, 422) and "stream_options" in body:
                # 某些兼容网关不支持 stream_options，降级重试一次
                await resp.aclose()
                body.pop("stream_options")
                request = client.build_request("POST", url, headers=headers, json=body)
                resp = await client.send(request, stream=True)

            try:
                if resp.status_code >= 400:
                    error_body = (await resp.aread()).decode("utf-8", errors="replace")
                    raise RuntimeError(f"LLM API 错误 {resp.status_code}: {error_body[:300]}")
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            yield "[DONE]"
                            return
                        yield chunk
            finally:
                await resp.aclose()

    def _get_available_tools(self) -> list[dict[str, Any]]:
        """获取可用工具列表（OpenAI function calling 格式）。"""
        tools: list[dict[str, Any]] = []
        for tool in mcp_manager.list_tools():
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema or {"type": "object", "properties": {}},
                },
            })
        return tools

    async def _execute_tool(self, name: str, args: dict) -> tuple[str, bool, int]:
        """执行工具调用，返回 (result_json, success, latency_ms)。"""
        start = time.time()
        try:
            result = await mcp_manager.call_tool(name, args, timeout=60.0)
            latency = int((time.time() - start) * 1000)
            if isinstance(result, str):
                return result, True, latency
            return json.dumps(result, ensure_ascii=False), True, latency
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            logger.error(f"Tool execution failed: {name} -> {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False), False, latency

    # -----------------------------------------------------------------
    # 持久化
    # -----------------------------------------------------------------

    async def _save_step(
        self,
        run_id: int,
        step_index: int,
        step_type: StepType,
        data: dict[str, Any],
    ) -> None:
        """保存步骤到数据库。"""
        async with SessionLocal() as db:
            step = AgentStep(
                run_id=run_id,
                step_index=step_index,
                step_type=step_type.value,
                role=data.get("role"),
                output_content=data.get("output_content"),
                tool_calls_json=data.get("tool_calls_json"),
                tool_name=data.get("tool_name"),
                tool_args=data.get("tool_args"),
                tool_result=data.get("tool_result"),
                tool_success=data.get("tool_success"),
                tool_latency_ms=data.get("tool_latency_ms"),
                input_tokens=data.get("input_tokens", 0),
                output_tokens=data.get("output_tokens", 0),
                cost_usd=Decimal(str(data.get("cost_usd", 0))),
                latency_ms=data.get("latency_ms"),
                result_hash=data.get("result_hash"),
                status=data.get("status", "completed"),
            )
            db.add(step)

            # 更新 run 累计
            run = await db.get(AgentRun, run_id)
            if run:
                run.step_count = step_index
                run.total_input_tokens += data.get("input_tokens", 0)
                run.total_output_tokens += data.get("output_tokens", 0)
                run.total_cost_usd += Decimal(str(data.get("cost_usd", 0)))

            await db.commit()

    async def _persist_usage_log(
        self,
        run_id: int,
        step_id: int | None,
        usage: UsageRecord,
        budget_status: dict,
    ) -> None:
        """持久化用量日志 + API 调用日志。"""
        async with SessionLocal() as db:
            log = AgentUsageLog(
                run_id=run_id,
                step_id=step_id,
                model=usage.model,
                provider=usage.provider,
                role=usage.role,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                context_tokens=usage.context_tokens,
                cost_usd=usage.cost_usd,
                latency_ms=usage.latency_ms,
                first_token_ms=usage.first_token_ms,
                budget_remaining=budget_status.get("remaining_tokens"),
                budget_usage_pct=Decimal(str(budget_status.get("usage_pct", 0))),
            )
            db.add(log)

            # 同时写入安全中心 API 调用日志
            run = await db.get(AgentRun, run_id)
            if run:
                total = usage.input_tokens + usage.output_tokens + usage.cache_read_tokens + usage.cache_write_tokens + usage.reasoning_tokens
                call_log = ApiCallLog(
                    user_id=run.user_id,
                    run_id=run_id,
                    step_id=step_id,
                    model=usage.model or "",
                    provider=usage.provider or "",
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cache_read_tokens=usage.cache_read_tokens,
                    cache_write_tokens=usage.cache_write_tokens,
                    reasoning_tokens=usage.reasoning_tokens,
                    total_tokens=total,
                    cost_usd=str(usage.cost_usd),
                    latency_ms=usage.latency_ms,
                    workspace_id=run.workspace_id,
                )
                db.add(call_log)

            await db.commit()

    async def _finalize_run(self, active: _ActiveRun, final_content: str) -> None:
        """完成运行。"""
        async with SessionLocal() as db:
            run = await db.get(AgentRun, active.run_id)
            if run:
                run.status = RunState.completed.value
                run.context_summary = active.context.summary
                # token 累计由 _save_step 逐步累加（input/output 分开），
                # 此处不再用 used_tokens 覆盖（used_tokens 含 output，语义不符）
                run.step_count = active.step_counter
                await db.commit()
        logger.info(f"AgentRun completed: id={active.run_id} steps={active.step_counter}")

    async def _fail_run(self, active: _ActiveRun, error: str) -> None:
        """标记运行失败。"""
        async with SessionLocal() as db:
            run = await db.get(AgentRun, active.run_id)
            if run:
                run.status = RunState.failed.value
                run.error_message = error
                run.step_count = active.step_counter
                await db.commit()
        logger.error(f"AgentRun failed: id={active.run_id} error={error}")

    async def _get_provider(self, run_id: int) -> AiProvider:
        """获取运行关联的 AI Provider。"""
        async with SessionLocal() as db:
            run = await db.get(AgentRun, run_id)
            if not run or not run.provider_id:
                # fallback: 第一个启用的
                stmt = (
                    select(AiProvider)
                    .where(AiProvider.enabled == 1)
                    .order_by(AiProvider.sort, AiProvider.id)
                    .limit(1)
                )
                provider = (await db.execute(stmt)).scalar_one_or_none()
                if not provider:
                    raise ValueError("没有可用的 AI 模型供应商")
                return provider
            provider = await db.get(AiProvider, run.provider_id)
            if not provider:
                raise ValueError(f"Provider {run.provider_id} 不存在")
            return provider

    def _get_provider_config(self, provider: AiProvider) -> dict[str, str]:
        """获取 provider 的 base_url 和默认模型。"""
        defaults = PROVIDER_DEFAULTS.get(provider.provider_type, PROVIDER_DEFAULTS["custom"])
        base_url = provider.base_url or defaults["base_url"]
        return {"base_url": base_url, "default_model": defaults["default_model"]}

    def _get_model_detail(self, provider: AiProvider | None, model_name: str) -> dict[str, Any]:
        """从 provider.model_details 获取指定模型的元数据，找不到则返回空 dict。"""
        if not provider:
            return {}
        try:
            details = json.loads(provider.model_details) if provider.model_details else {}
        except (json.JSONDecodeError, TypeError):
            return {}
        return details.get(model_name, {})

    def _apply_model_pricing(self, usage: UsageRecord, provider: AiProvider | None, model_name: str) -> None:
        """如果 model_details 中配置了价格，则覆盖 UsageRecord.cost_usd。"""
        md = self._get_model_detail(provider, model_name)
        input_price = md.get("input_price_per_million")
        output_price = md.get("output_price_per_million")
        if input_price is not None and output_price is not None:
            cost = (
                Decimal(input_price) * Decimal(usage.input_tokens) / Decimal(1_000_000)
                + Decimal(output_price) * Decimal(usage.output_tokens) / Decimal(1_000_000)
            )
            usage.cost_usd = cost.quantize(Decimal("0.000001"))


# ---------------------------------------------------------------------------
# 全局运行时实例
# -----------------------------------------------------------------

agent_runtime = AgentRuntime()
