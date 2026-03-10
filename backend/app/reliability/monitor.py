"""
自我监控系统 - 目标设定、进度追踪、偏离检测
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SelfMonitor:
    """自我监控系统"""

    def __init__(self):
        self.goal = ""
        self.plan: List[Dict[str, str]] = []
        self.checkpoints: List[Dict[str, Any]] = []
        self.current_step_index = 0

    def set_goal(self, goal: str, estimated_steps: int = 5):
        """设置目标和预估步骤数"""
        self.goal = goal
        self.plan = [
            {"step": f"Step {i+1}", "status": "pending", "description": ""}
            for i in range(estimated_steps)
        ]
        self.current_step_index = 0
        logger.info(f"Goal set: {goal} ({estimated_steps} steps)")

    def set_plan(self, steps: List[str]):
        """设置详细计划"""
        self.plan = [
            {"step": f"Step {i+1}", "status": "pending", "description": desc}
            for i, desc in enumerate(steps)
        ]

    def mark_step_done(self, step_index: Optional[int] = None):
        """标记步骤完成"""
        if step_index is None:
            step_index = self.current_step_index

        if 0 <= step_index < len(self.plan):
            self.plan[step_index]["status"] = "done"
            if step_index == self.current_step_index:
                self.current_step_index += 1
            logger.info(f"Step {step_index+1} marked as done")

    def get_progress(self) -> float:
        """获取进度百分比"""
        if not self.plan:
            return 0.0
        done = sum(1 for s in self.plan if s["status"] == "done")
        return done / len(self.plan)

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "goal": self.goal,
            "progress": f"{self.get_progress():.0%}",
            "current_step": self.current_step_index + 1,
            "total_steps": len(self.plan),
            "plan": self.plan,
            "checkpoints": len(self.checkpoints)
        }

    async def check_on_track(self, llm) -> Dict[str, Any]:
        """检查是否偏离目标（需要 LLM）"""
        from langchain_core.messages import HumanMessage

        prompt = f"""Goal: {self.goal}
Progress: {self.get_progress():.0%}
Plan: {json.dumps(self.plan, ensure_ascii=False)}

Analyze if we are on track. Return ONLY valid JSON:
{{
  "on_track": true/false,
  "reason": "brief explanation",
  "suggestion": "what to do next"
}}"""

        try:
            result = await llm.ainvoke([HumanMessage(content=prompt)])
            check = json.loads(result.content.strip().strip("```json").strip("```"))
        except Exception as e:
            logger.error(f"Check failed: {e}")
            check = {"on_track": True, "reason": "check failed", "suggestion": "continue"}

        # 记录检查点
        self.checkpoints.append({
            "timestamp": datetime.now().isoformat(),
            "progress": self.get_progress(),
            "on_track": check.get("on_track", True),
            "reason": check.get("reason", "")
        })

        return check

    def should_check(self, tool_count: int, check_interval: int = 3) -> bool:
        """判断是否应该进行检查"""
        return tool_count > 0 and tool_count % check_interval == 0


# 全局实例
_global_monitor = SelfMonitor()


def get_monitor() -> SelfMonitor:
    """获取全局监控实例"""
    return _global_monitor
