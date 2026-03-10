from __future__ import annotations
import logging
import re
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from backend.app.llm import get_llm
from backend.app.tools.implementations.search_tool import web_search

logger = logging.getLogger(__name__)

G = "\033[90m"
R = "\033[0m"

BUDGET = {"simple": 4, "medium": 5, "hard": 10, "extreme": 15}
MAX_TOOL_CALLS = 20

TOOLS = [web_search]


class SearchSubagent:
    """
    单条查询的搜索 agent，运行在独立上下文中。

    使用 tool-calling 循环：LLM 自主决定调用 web_search / fetch_url，
    直到信息充足或达到预算上限。
    由 SearchLeadAgent 并行调用，每次调用创建新实例（独立上下文）。
    """

    def __init__(self, difficulty: str = "medium"):
        self._llm = get_llm().bind_tools(TOOLS)
        self._tools_map = {t.name: t for t in TOOLS}
        self._max_iter = BUDGET.get(difficulty, BUDGET["medium"])
        self._tool_calls = 0

    def run(self, query: str, topic: str = "", research_dir: Path | None = None) -> str:
        print(f"{G}      🔎 [SubAgent] start: {query} (budget={self._max_iter}){R}")

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        system = (
            f"Current time: {current_time}\n\n"
            "You are a research agent. Use web_search to thoroughly research the query.\n"
            "Search multiple angles and keywords to gather comprehensive information.\n"
            f"Budget: up to {self._max_iter} rounds of tool calls."
        )
        if topic:
            system += f"\nResearch context: {topic}"

        messages = [
            SystemMessage(content=system),
            HumanMessage(content=f"Research: {query}"),
        ]
        resp = None

        for i in range(self._max_iter):
            if self._tool_calls >= MAX_TOOL_CALLS:
                print(f"{G}      🔎 [SubAgent] tool_calls limit reached{R}")
                break

            resp = self._llm.invoke(messages)
            messages.append(resp)

            if not resp.tool_calls:
                break

            for tc in resp.tool_calls:
                if self._tool_calls >= MAX_TOOL_CALLS:
                    break
                self._tool_calls += 1
                result = self._tools_map[tc["name"]].invoke(tc["args"])
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                print(f"{G}      🔎 [SubAgent] iter={i + 1} {tc['name']}{R}")

        # 预算耗尽时 resp 可能是 tool_calls，需要补一次 final summary
        if resp is None or resp.tool_calls:
            resp = get_llm().invoke(messages + [HumanMessage(content="Summarize all findings.")])

        results_text = resp.content

        if research_dir is not None:
            return _write_subagent_results(query, results_text, research_dir)
        return results_text


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_subagent_results(query: str, content: str, research_dir: Path) -> str:
    """将 SubAgent 结果写入文件，返回文件路径字符串。"""
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", query)[:40]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    file_path = research_dir / f"sub_{slug}_{timestamp}.md"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(f"# SubAgent: {query}\n\n{content}")
    return str(file_path)
