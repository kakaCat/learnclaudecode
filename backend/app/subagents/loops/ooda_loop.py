"""
OODA 执行循环
"""
import json
import logging
from typing import Tuple, Any, List

from langchain_core.messages import SystemMessage, HumanMessage

from .base import BaseLoop
from ..config import CONFIG
from ..utils.console import console
from ..exceptions import LoopExecutionError, ToolInvocationError
from backend.app.core.tracer import Tracer

logger = logging.getLogger(__name__)
tracer = Tracer()


class OODALoop(BaseLoop):
    """
    OODA (Observe-Orient-Decide-Act) 执行循环

    循环执行四个阶段：
    1. Observe: 收集信息
    2. Orient: 分析情况
    3. Decide: 决策下一步
    4. Act: 执行动作

    适用于需要迭代探索的不确定任务。
    """

    def run(
        self,
        llm: Any,
        tools: list,
        system_prompt: str,
        user_prompt: str,
        span_id: str,
        subagent_type: str,
        max_cycles: int = None,
    ) -> Tuple[str, int]:
        """
        执行 OODA 循环

        Args:
            llm: LLM 实例
            tools: 工具列表
            system_prompt: 系统提示词
            user_prompt: 用户输入
            span_id: Tracer span ID
            subagent_type: Subagent 类型
            max_cycles: 最大循环次数（可选，默认使用配置）

        Returns:
            (output, tool_count)
        """
        # 验证输入
        self._validate_inputs(llm, tools, system_prompt, user_prompt)

        if max_cycles is None:
            max_cycles = CONFIG.MAX_OODA_CYCLES

        self._log_start(subagent_type, user_prompt)

        try:
            output, tool_count = self._execute_loop(
                llm=llm,
                tools=tools,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                span_id=span_id,
                subagent_type=subagent_type,
                max_cycles=max_cycles,
            )

            self._log_end(subagent_type, tool_count, len(output))
            return output, tool_count

        except Exception as e:
            self._handle_error(e, subagent_type)

    def _execute_loop(
        self,
        llm: Any,
        tools: list,
        system_prompt: str,
        user_prompt: str,
        span_id: str,
        subagent_type: str,
        max_cycles: int,
    ) -> Tuple[str, int]:
        """执行 OODA 循环的核心逻辑"""
        tool_count = 0
        tool_map = {t.name: t for t in tools}
        observations: List[str] = []
        history: List[str] = []

        for cycle in range(1, max_cycles + 1):
            console.ooda_cycle(cycle, max_cycles)
            tracer.emit(
                "ooda.cycle",
                span_id=span_id,
                agent_type=subagent_type,
                cycle=cycle
            )

            # 每 N 个 cycle 压缩一次 observations
            if cycle > 1 and cycle % CONFIG.OODA_COMPRESSION_INTERVAL == 0:
                observations = self._compress_observations(
                    llm, system_prompt, observations, subagent_type
                )

            # ── Phase 1: Observe ──
            obs_tools = self._observe_phase(
                llm, system_prompt, user_prompt, observations, tool_map
            )
            if obs_tools:
                obs_results = self._invoke_tools(obs_tools, tool_map)
                tool_count += len(obs_results)
                observations.extend(obs_results)

            # ── Phase 2: Orient ──
            situation = self._orient_phase(
                llm, system_prompt, user_prompt, observations
            )
            confidence = situation.get("confidence", 0.5)
            console.ooda_decision("ORIENT", confidence)

            # ── Phase 3: Decide ──
            decision = self._decide_phase(
                llm, system_prompt, user_prompt, situation
            )
            choice = decision.get("choice", "DONE")
            console.ooda_decision(choice, confidence)

            if choice == "DONE":
                break

            # ── Phase 4: Act ──
            if choice == "ACT":
                act_tools = self._act_phase(
                    llm, system_prompt, user_prompt, situation, tool_map
                )
                if act_tools:
                    act_results = self._invoke_tools(act_tools, tool_map)
                    tool_count += len(act_results)
                    history.extend(act_results)

        # 生成最终总结
        output = self._generate_summary(
            llm, system_prompt, user_prompt, observations, history
        )

        return output, tool_count

    def _observe_phase(
        self,
        llm: Any,
        system_prompt: str,
        goal: str,
        observations: List[str],
        tool_map: dict,
    ) -> List[dict]:
        """
        Observe 阶段：决定调用哪些工具收集信息

        Returns:
            工具调用列表 [{"name": "...", "args": {...}}, ...]
        """
        prompt = (
            f"Goal: {goal}\n"
            f"Previous observations: {observations}\n\n"
            f"Available tools: {list(tool_map.keys())}\n\n"
            "OBSERVE phase: decide which tools to call to gather information.\n"
            'Output ONLY valid JSON: {"tools": [{"name": "...", "args": {...}}]}\n'
            'If no tools needed, output: {"tools": []}'
        )

        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])

        try:
            result = json.loads(resp.content.strip().strip("```json").strip("```"))
            return result.get("tools", [])
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse OBSERVE response: {e}")
            return []

    def _orient_phase(
        self,
        llm: Any,
        system_prompt: str,
        goal: str,
        observations: List[str],
    ) -> dict:
        """
        Orient 阶段：分析观察结果

        Returns:
            {"situation": "...", "gaps": [...], "confidence": 0.0-1.0}
        """
        prompt = (
            f"Goal: {goal}\n"
            f"Observations so far: {observations}\n\n"
            "ORIENT phase: analyze the observations.\n"
            'Output ONLY valid JSON: {"situation": "...", "gaps": [...], "confidence": 0.0-1.0}'
        )

        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])

        try:
            return json.loads(resp.content.strip().strip("```json").strip("```"))
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse ORIENT response: {e}")
            return {
                "situation": resp.content.strip(),
                "gaps": [],
                "confidence": 0.5
            }

    def _decide_phase(
        self,
        llm: Any,
        system_prompt: str,
        goal: str,
        situation: dict,
    ) -> dict:
        """
        Decide 阶段：决定下一步行动

        Returns:
            {"choice": "OBSERVE_MORE"|"ACT"|"DONE", "reason": "..."}
        """
        prompt = (
            f"Goal: {goal}\n"
            f"Situation: {situation}\n\n"
            "DECIDE phase: choose next step.\n"
            'Output ONLY valid JSON: {"choice": "OBSERVE_MORE"|"ACT"|"DONE", "reason": "..."}'
        )

        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])

        try:
            return json.loads(resp.content.strip().strip("```json").strip("```"))
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse DECIDE response: {e}")
            return {
                "choice": "DONE",
                "reason": resp.content.strip()
            }

    def _act_phase(
        self,
        llm: Any,
        system_prompt: str,
        goal: str,
        situation: dict,
        tool_map: dict,
    ) -> List[dict]:
        """
        Act 阶段：执行动作

        Returns:
            工具调用列表
        """
        prompt = (
            f"Goal: {goal}\n"
            f"Situation: {situation}\n\n"
            f"Available tools: {list(tool_map.keys())}\n\n"
            "ACT phase: execute the action using tools.\n"
            'Output ONLY valid JSON: {"tools": [{"name": "...", "args": {...}}]}'
        )

        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])

        try:
            result = json.loads(resp.content.strip().strip("```json").strip("```"))
            return result.get("tools", [])
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse ACT response: {e}")
            return []

    def _invoke_tools(self, tool_calls: List[dict], tool_map: dict) -> List[str]:
        """
        执行工具调用

        Args:
            tool_calls: [{"name": "...", "args": {...}}, ...]
            tool_map: {tool_name: tool_instance}

        Returns:
            结果字符串列表
        """
        results = []
        for tc in tool_calls:
            tool_name = tc.get("name")
            tool = tool_map.get(tool_name)

            if not tool:
                results.append(f"Error: unknown tool {tool_name}")
                continue

            try:
                result = tool.invoke(tc.get("args", {}))
                result_str = str(result)[:CONFIG.TOOL_RESULT_MAX_LENGTH]
                results.append(result_str)
                console.tool_result("OODA", result_str)
            except Exception as e:
                error_msg = f"Error: {e}"
                results.append(error_msg)
                logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)

        return results

    def _compress_observations(
        self,
        llm: Any,
        system_prompt: str,
        observations: List[str],
        subagent_type: str,
    ) -> List[str]:
        """
        压缩观察结果列表

        Args:
            llm: LLM 实例
            system_prompt: 系统提示词
            observations: 观察结果列表
            subagent_type: Subagent 类型

        Returns:
            压缩后的观察结果列表（单条总结）
        """
        if len(observations) <= CONFIG.OBSERVATION_COMPRESSION_LIMIT:
            return observations

        obs_text = "\n".join(
            f"- {obs[:CONFIG.OBSERVATION_PREVIEW_LENGTH]}"
            for obs in observations
        )

        summary_resp = llm.invoke([
            SystemMessage(content="你是一个信息总结助手"),
            HumanMessage(content=f"请简洁总结以下观察结果，保留关键信息：\n\n{obs_text}")
        ])

        console.gray(
            f"   🗜️ [OODA] 压缩 observations: {len(observations)} → 1 条总结"
        )

        return [f"[总结] {summary_resp.content}"]

    def _generate_summary(
        self,
        llm: Any,
        system_prompt: str,
        goal: str,
        observations: List[str],
        history: List[str],
    ) -> str:
        """
        生成最终总结

        Args:
            llm: LLM 实例
            system_prompt: 系统提示词
            goal: 目标
            observations: 观察结果
            history: 执行历史

        Returns:
            总结文本
        """
        prompt = (
            f"Goal: {goal}\n"
            f"Observations: {observations}\n"
            f"Actions taken: {history}\n\n"
            "Summarize what was accomplished concisely."
        )

        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])

        return resp.content.strip()
