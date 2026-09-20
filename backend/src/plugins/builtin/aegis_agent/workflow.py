"""AegisCode Agent 多角色 DAG 工作流。

四角色 DAG（Planner → Coder → Reviewer → Tester）:
1. Planner: 分析任务，生成 subtask DAG
2. Coder: 执行编码任务（可并行/串行，按 DAG 依赖）
3. Reviewer: 审阅代码变更
4. Tester: 运行测试验证

参考:
- OpenHands: task decomposition — 任务分解为子任务
- Aider: git-diff 反馈 — diff 有变化作为进展信号
- 原实现: agent_workflow.py 四角色 DAG（保留角色协议，调度简化）

设计:
- 每个 subtask 独立上下文窗口（避免长任务上下文膨胀）
- 角色间通过结构化协议通信
- write_scope 声明：Coder 声明要写的文件，冲突时串行
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from loguru import logger

from src.core.crypto import decrypt_api_key


# ---------------------------------------------------------------------------
# 角色定义
# ---------------------------------------------------------------------------

class AgentRole(str, Enum):
    planner = "planner"
    coder = "coder"
    reviewer = "reviewer"
    tester = "tester"


# ---------------------------------------------------------------------------
# 角色提示词
# ---------------------------------------------------------------------------

ROLE_PROMPTS: dict[str, str] = {
    "planner": """你是 AegisCode Planner，负责任务分析与分解。

职责:
1. 理解用户需求，分析技术可行性
2. 将任务分解为有序的子任务（subtask DAG）
3. 每个子任务描述清晰：目标、涉及文件、预期结果

输出格式（JSON）:
```json
{
  "subtasks": [
    {
      "id": "task_1",
      "description": "创建用户登录API",
      "files": ["backend/api/auth.py", "backend/models/user.py"],
      "dependencies": [],
      "role": "coder"
    }
  ]
}
```
""",

    "coder": """你是 AegisCode Coder，负责编码实现。

职责:
1. 根据 subtask 描述编写代码
2. 使用工具创建/修改文件
3. 每次修改后给出简洁总结

规则:
- 声明 write_scope: 告知将修改哪些文件
- 遵循项目现有代码风格
- 修改后用 git status 确认变更
""",

    "reviewer": """你是 AegisCode Reviewer，负责代码审阅。

职责:
1. 审阅 Coder 的代码变更
2. 检查代码质量、安全性、规范性
3. 给出审阅结论: approved / needs_revision

输出格式:
```json
{
  "verdict": "approved" | "needs_revision",
  "issues": [
    {"severity": "high/medium/low", "file": "path", "line": 42, "comment": "..."}
  ],
  "summary": "总体评价"
}
```
""",

    "tester": """你是 AegisCode Tester，负责测试验证。

职责:
1. 运行项目测试命令
2. 验证功能正确性
3. 报告测试结果

输出格式:
```json
{
  "passed": true/false,
  "tests_run": 10,
  "tests_passed": 9,
  "failures": ["test_login: 断言失败 line 42"],
  "summary": "9/10 通过，1个失败"
}
```
""",
}


# ---------------------------------------------------------------------------
# Subtask DAG
# ---------------------------------------------------------------------------

@dataclass
class Subtask:
    """DAG 中的子任务节点。"""
    id: str
    description: str
    role: str = "coder"           # coder/reviewer/tester
    files: list[str] = field(default_factory=list)  # 涉及文件
    dependencies: list[str] = field(default_factory=list)  # 依赖的子任务ID
    status: str = "pending"       # pending/running/completed/failed/skipped
    result: str = ""              # 执行结果
    write_scope: list[str] = field(default_factory=list)  # 声明要写的文件


@dataclass
class SubtaskDAG:
    """子任务 DAG。"""
    subtasks: list[Subtask] = field(default_factory=list)

    def get_ready_tasks(self) -> list[Subtask]:
        """获取所有依赖已完成的待执行任务。"""
        completed_ids = {s.id for s in self.subtasks if s.status == "completed"}
        return [
            s for s in self.subtasks
            if s.status == "pending"
            and all(dep in completed_ids for dep in s.dependencies)
        ]

    def all_completed(self) -> bool:
        return all(s.status in ("completed", "skipped") for s in self.subtasks)

    def has_failed(self) -> bool:
        return any(s.status == "failed" for s in self.subtasks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subtasks": [
                {
                    "id": s.id, "description": s.description, "role": s.role,
                    "files": s.files, "dependencies": s.dependencies,
                    "status": s.status, "result": s.result[:500],
                }
                for s in self.subtasks
            ]
        }


# ---------------------------------------------------------------------------
# Write Scope 冲突管理
# ---------------------------------------------------------------------------

class WriteScopeManager:
    """write_scope 冲突管理——冲突的 coder 任务串行执行。

    原实现合理，保留:
    - Coder 声明要写的文件列表
    - 如果两个任务要写同一文件，必须串行
    - 不同文件的任务可以并行
    """

    def __init__(self):
        self._locked_files: dict[str, str] = {}  # file_path → task_id
        self._lock = asyncio.Lock()

    async def acquire(self, task_id: str, files: list[str]) -> bool:
        """尝试获取文件写锁。"""
        async with self._lock:
            # 检查冲突
            for f in files:
                if f in self._locked_files and self._locked_files[f] != task_id:
                    return False
            # 获取锁
            for f in files:
                self._locked_files[f] = task_id
            return True

    async def release(self, task_id: str) -> None:
        """释放文件写锁。"""
        async with self._lock:
            self._locked_files = {
                f: tid for f, tid in self._locked_files.items() if tid != task_id
            }


# ---------------------------------------------------------------------------
# 工作流引擎
# ---------------------------------------------------------------------------

class WorkflowEngine:
    """Planner DAG 四角色工作流引擎。

    流程:
    1. Planner 分析任务 → 生成 subtask DAG
    2. 按 DAG 依赖调度子任务:
       - 无依赖的任务可以并行
       - write_scope 冲突的任务串行
    3. 每个子任务完成后，Reviewer 审阅
    4. 所有子任务完成后，Tester 验证
    5. 如果 Reviewer 或 Tester 失败，反馈给 Planner 重新规划
    """

    def __init__(self, runtime: Any):
        """Args:
            runtime: AgentRuntime 实例（提供 LLM 调用能力）
        """
        self.runtime = runtime
        self.scope_manager = WriteScopeManager()
        self._max_replans: int = 3  # 最大重新规划次数

    async def execute_dag_workflow(
        self,
        run_id: int,
        user_content: str,
    ) -> dict[str, Any]:
        """执行完整的 DAG 工作流。

        Returns:
            {"status": "completed/failed", "dag": {...}, "results": [...]}
        """
        from src.plugins.builtin.aegis_agent.runtime import agent_runtime

        active = agent_runtime._active_runs.get(run_id)
        if not active:
            raise ValueError(f"Run {run_id} not active")

        # Phase 1: Planner 分析
        dag = await self._run_planner(active, user_content)
        if not dag:
            return {"status": "failed", "reason": "Planner 未能生成任务分解"}

        yield_event = {
            "type": "dag_created",
            "dag": dag.to_dict(),
        }

        # Phase 2: 执行子任务
        replan_count = 0
        while not dag.all_completed() and not dag.has_failed():
            ready = dag.get_ready_tasks()
            if not ready:
                if not dag.all_completed():
                    logger.warning("DAG deadlock: no ready tasks but not all completed")
                    break
                continue

            # 尝试并行执行（write_scope 冲突的串行）
            tasks_to_run = await self._schedule_tasks(ready)

            for subtask in tasks_to_run:
                subtask.status = "running"

                # 执行子任务
                result = await self._execute_subtask(active, subtask)

                if result.get("success"):
                    subtask.status = "completed"
                    subtask.result = result.get("content", "")

                    # Reviewer 审阅
                    review = await self._run_reviewer(active, subtask)
                    if review.get("verdict") == "needs_revision":
                        # 反馈给 Coder 重新执行
                        subtask.status = "pending"  # 重新加入队列
                        logger.info(f"Subtask {subtask.id} needs revision")
                else:
                    subtask.status = "failed"
                    subtask.result = result.get("error", "")

                # 释放 write_scope
                await self.scope_manager.release(subtask.id)

            # 检查是否需要重新规划
            if dag.has_failed() and replan_count < self._max_replans:
                replan_count += 1
                logger.info(f"Replanning ({replan_count}/{self._max_replans})")
                failed_tasks = [s for s in dag.subtasks if s.status == "failed"]
                new_dag = await self._replan(active, dag, failed_tasks)
                if new_dag:
                    dag = new_dag

        # Phase 3: Tester 验证
        if dag.all_completed():
            test_result = await self._run_tester(active, dag)
            return {
                "status": "completed" if test_result.get("passed") else "completed_with_issues",
                "dag": dag.to_dict(),
                "test_result": test_result,
            }

        return {"status": "failed", "dag": dag.to_dict()}

    # -----------------------------------------------------------------
    # 角色执行
    # -----------------------------------------------------------------

    async def _run_planner(self, active: Any, user_content: str) -> SubtaskDAG | None:
        """Planner 分析任务并生成 DAG。"""
        # 添加 Planner 消息到上下文（修复: 角色提示词必须注入 system 层，
        # 之前 prompt 变量构建后未传给 LLM 属于死代码）
        role_prompt = ROLE_PROMPTS["planner"]
        active.context.add_user_message(
            f"{role_prompt}\n\n[Planner] 请分析以下任务并分解为子任务: {user_content}"
        )

        # 调用 LLM
        llm_messages = active.context.build_llm_messages()
        provider = await self.runtime._get_provider(active.run_id)
        api_key = decrypt_api_key(provider.api_key_enc)
        config = self.runtime._get_provider_config(provider)

        response = await self.runtime._call_llm(
            llm_messages, api_key, config["base_url"],
            provider, active,
        )

        content = response["choices"][0]["message"].get("content", "")
        active.context.add_assistant_message(content)

        # 解析 DAG
        return self._parse_dag(content)

    async def _execute_subtask(self, active: Any, subtask: Subtask) -> dict[str, Any]:
        """执行单个子任务（Coder 角色）。"""
        role_prompt = ROLE_PROMPTS["coder"]
        active.context.add_user_message(
            f"{role_prompt}\n\n[Coder] 任务: {subtask.description}\n\n"
            f"涉及文件: {', '.join(subtask.files) if subtask.files else '（由你判断）'}"
        )

        # 运行对话循环（复用 runtime 的工具循环）
        # 这里简化为单轮调用
        llm_messages = active.context.build_llm_messages()
        provider = await self.runtime._get_provider(active.run_id)
        api_key = decrypt_api_key(provider.api_key_enc)
        config = self.runtime._get_provider_config(provider)

        try:
            response = await self.runtime._call_llm(
                llm_messages, api_key, config["base_url"],
                provider, active,
            )
            content = response["choices"][0]["message"].get("content", "")
            active.context.add_assistant_message(content)
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _run_reviewer(self, active: Any, subtask: Subtask) -> dict[str, Any]:
        """Reviewer 审阅子任务结果。"""
        role_prompt = ROLE_PROMPTS["reviewer"]
        active.context.add_user_message(
            f"{role_prompt}\n\n[Reviewer] 审阅任务: {subtask.description}\n\n"
            f"任务结果: {subtask.result[:2000]}"
        )

        llm_messages = active.context.build_llm_messages()
        provider = await self.runtime._get_provider(active.run_id)
        api_key = decrypt_api_key(provider.api_key_enc)
        config = self.runtime._get_provider_config(provider)

        try:
            response = await self.runtime._call_llm(
                llm_messages, api_key, config["base_url"],
                provider, active,
            )
            content = response["choices"][0]["message"].get("content", "")
            active.context.add_assistant_message(content)

            # 解析审阅结果
            try:
                review_data = json.loads(content)
                return review_data
            except json.JSONDecodeError:
                return {"verdict": "approved", "summary": content[:200]}
        except Exception as e:
            return {"verdict": "needs_revision", "issues": [{"comment": str(e)}]}

    async def _run_tester(self, active: Any, dag: SubtaskDAG) -> dict[str, Any]:
        """Tester 运行测试验证。"""
        role_prompt = ROLE_PROMPTS["tester"]
        completed_desc = "\n".join(
            f"- {s.id}: {s.description}" for s in dag.subtasks
        )
        active.context.add_user_message(
            f"{role_prompt}\n\n[Tester] 请验证所有任务结果。\n\n已完成的子任务:\n{completed_desc}"
        )

        llm_messages = active.context.build_llm_messages()
        provider = await self.runtime._get_provider(active.run_id)
        api_key = decrypt_api_key(provider.api_key_enc)
        config = self.runtime._get_provider_config(provider)

        try:
            response = await self.runtime._call_llm(
                llm_messages, api_key, config["base_url"],
                provider, active,
            )
            content = response["choices"][0]["message"].get("content", "")
            active.context.add_assistant_message(content)

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"passed": True, "summary": content[:200]}
        except Exception as e:
            return {"passed": False, "failures": [str(e)]}

    async def _replan(self, active: Any, dag: SubtaskDAG, failed_tasks: list[Subtask]) -> SubtaskDAG | None:
        """重新规划失败的任务。"""
        failed_desc = "\n".join(
            f"- {s.id} (失败原因: {s.result[:200]})" for s in failed_tasks
        )
        role_prompt = ROLE_PROMPTS["planner"]
        active.context.add_user_message(
            f"{role_prompt}\n\n[Planner] 以下任务失败了，请重新规划:\n{failed_desc}"
        )

        llm_messages = active.context.build_llm_messages()
        provider = await self.runtime._get_provider(active.run_id)
        api_key = decrypt_api_key(provider.api_key_enc)
        config = self.runtime._get_provider_config(provider)

        try:
            response = await self.runtime._call_llm(
                llm_messages, api_key, config["base_url"],
                provider, active,
            )
            content = response["choices"][0]["message"].get("content", "")
            active.context.add_assistant_message(content)
            return self._parse_dag(content)
        except Exception as e:
            logger.error(f"Replan failed: {e}")
            return None

    # -----------------------------------------------------------------
    # 调度
    # -----------------------------------------------------------------

    async def _schedule_tasks(self, ready: list[Subtask]) -> list[Subtask]:
        """调度就绪任务，处理 write_scope 冲突。"""
        scheduled: list[Subtask] = []

        for subtask in ready:
            # 尝试获取 write_scope 锁
            if subtask.write_scope:
                acquired = await self.scope_manager.acquire(subtask.id, subtask.write_scope)
                if not acquired:
                    logger.debug(f"Subtask {subtask.id} waiting for write_scope")
                    continue
            scheduled.append(subtask)

        return scheduled

    # -----------------------------------------------------------------
    # DAG 解析
    # -----------------------------------------------------------------

    def _parse_dag(self, content: str) -> SubtaskDAG | None:
        """从 LLM 输出解析 DAG。

        尝试从 content 中提取 JSON 块。
        """
        # 尝试提取 ```json ... ``` 块
        import re
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                return None
        else:
            # 尝试直接解析
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return None

        subtasks_data = data.get("subtasks", [])
        if not subtasks_data:
            return None

        dag = SubtaskDAG()
        for st in subtasks_data:
            subtask = Subtask(
                id=st.get("id", f"task_{len(dag.subtasks)+1}"),
                description=st.get("description", ""),
                role=st.get("role", "coder"),
                files=st.get("files", []),
                dependencies=st.get("dependencies", []),
                write_scope=st.get("files", []),  # write_scope = files
            )
            dag.subtasks.append(subtask)

        logger.info(f"DAG parsed: {len(dag.subtasks)} subtasks")
        return dag
