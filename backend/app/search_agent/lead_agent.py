from __future__ import annotations
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from backend.app.llm import get_llm
from backend.app.search_agent.search_subagent import SearchSubagent
from backend.app.search_agent.citation_agent import CitationAgent
from backend.app.search.duckduckgo import DuckDuckGoSearch

logger = logging.getLogger(__name__)

G = "\033[90m"
R = "\033[0m"

DEFAULT_RESEARCH_DIR = Path("scripts/research")

# 查询类型 → subagent 数量上限
_SUBAGENT_COUNT = {"direct": 1, "broad": 3, "deep": 5}
# 查询类型 → subagent difficulty
_DIFFICULTY = {"direct": "simple", "broad": "medium", "deep": "hard"}


class SearchLeadAgent:
    """
    研究编排 agent，遵循「评估-分类-计划-执行」四步循环。

    pre-loop:
      评估  → probe()     探索信息版图，理解数据结构
      分类  → classify()  判断查询类型（direct / broad / deep）

    loop (up to MAX_CYCLES):
      计划  → _plan_queries()        按类型生成查询，针对 gaps 补搜
      执行  → _dispatch()            并行 spawn SearchSubagent
      监控  → _evaluate_coverage()   评估覆盖度，识别信息缺口
      适应  → _adapt()               贝叶斯更新：继续 or 止损综合

    搜索结果存入文件系统，仅向调用方返回轻量级文件路径。
    Lead 不执行初级搜索，只负责规划、委派、整合。
    """

    MAX_CYCLES = 4

    def __init__(self):
        self._llm = get_llm()
        self._ddg = DuckDuckGoSearch(max_results=3)   # 仅用于探索模式 probe
        self._citation = CitationAgent()

    def run(self, topic: str, research_dir: Path | None = None) -> str:
        print(f"{G}🔍 [SearchLeadAgent] topic: {topic}{R}")
        _research_dir = research_dir or DEFAULT_RESEARCH_DIR
        self._research_dir = _research_dir   # 供 _dispatch 传给 SubAgent

        # ── 探索模式：委派前先 probe，理解信息版图 ────────────────────────────
        probe_hint = self._probe(topic)
        print(f"{G}   🔭 probe hint: {probe_hint[:120]}{R}")

        # ── 查询类型分类 ──────────────────────────────────────────────────────
        query_type = self._classify(topic, probe_hint)
        max_subagents = _SUBAGENT_COUNT.get(query_type, 3)
        difficulty = _DIFFICULTY.get(query_type, "medium")
        print(f"{G}   🏷  type={query_type}, max_subagents={max_subagents}, difficulty={difficulty}{R}")

        memory: dict = {
            "topic": topic,
            "query_type": query_type,
            "cycles": [],
            "searched": [],
        }
        all_results: dict[str, str] = {}

        for cycle in range(1, self.MAX_CYCLES + 1):
            print(f"{G}   🔄 [Research] cycle {cycle}/{self.MAX_CYCLES}{R}")

            # ── 计划：生成本轮查询，针对 gaps 补搜 ───────────────────────────
            gaps = memory["cycles"][-1]["gaps"] if memory["cycles"] else []
            queries = self._plan_queries(topic, memory["searched"], all_results, gaps, query_type)
            new_queries = [q for q in queries if q not in memory["searched"]]
            new_queries = new_queries[:max_subagents]

            # ── 执行：并行 dispatch subagent ──────────────────────────────────
            if new_queries:
                print(f"{G}   📤 dispatch ({len(new_queries)}): {new_queries}{R}")
                batch = self._dispatch(new_queries, topic=topic, difficulty=difficulty)
                all_results.update(batch)
                memory["searched"].extend(new_queries)

            # ── 监控：评估覆盖度，识别信息缺口 ───────────────────────────────
            situation = self._evaluate_coverage(topic, all_results)
            confidence = situation.get("confidence", 0.5)
            gaps = situation.get("gaps", [])
            print(f"{G}   📊 confidence={confidence:.2f}, gaps={gaps}{R}")
            memory["cycles"].append({"cycle": cycle, "confidence": confidence, "gaps": gaps})

            # ── 适应：贝叶斯更新，决定继续还是止损综合 ───────────────────────
            choice = self._adapt(situation, cycle, memory["searched"])
            print(f"{G}   🎯 adapt={choice}{R}")

            if choice == "SYNTHESIZE":
                break

        path = self._synthesize(topic, all_results, memory, _research_dir)
        self._citation.run(path)
        print(f"{G}   ✅ saved → {path}{R}")
        return path

    # ── 探索模式 ──────────────────────────────────────────────────────────────

    def _probe(self, topic: str) -> str:
        """委派前先用1次搜索探索信息版图，只返回标题+URL列表，供 classify 判断查询类型。"""
        raw = self._ddg.search(topic)
        lines = [f"{i}. {r['title']} — {r['url']}" for i, r in enumerate(raw, 1)]
        return "\n".join(lines)

    # ── 查询类型分类 ──────────────────────────────────────────────────────────

    def _classify(self, topic: str, probe_hint: str) -> str:
        """
        判断查询类型：
        - direct: 聚焦、定义明确，单次调查即可
        - broad:  独立子问题，需要分头抓取数据再汇总
        - deep:   多视角深挖单一话题，需要平行探索不同观点
        """
        resp = self._llm.invoke([
            SystemMessage(content=(
                "Classify the research topic into one of three types.\n"
                'Output ONLY valid JSON: {"type": "direct" | "broad" | "deep", "reason": "one sentence"}\n'
                "- direct: focused, well-defined, single investigation suffices\n"
                "- broad: multiple independent sub-questions, need parallel data gathering\n"
                "- deep: single topic requiring multi-perspective analysis"
            )),
            HumanMessage(content=f"Topic: {topic}\n\nProbe results:\n{probe_hint[:1000]}"),
        ])
        try:
            raw = resp.content.strip().strip("```json").strip("```").strip()
            return json.loads(raw).get("type", "broad")
        except (json.JSONDecodeError, AttributeError):
            return "broad"

    # ── 研究循环四阶段 ────────────────────────────────────────────────────────

    def _plan_queries(
        self,
        topic: str,
        searched: list[str],
        results: dict[str, str],
        gaps: list[str],
        query_type: str,
    ) -> list[str]:
        # 按查询类型给 LLM 不同的规划策略
        strategy = {
            "direct": "Generate 1 focused query that directly answers the topic.",
            "broad":  "Decompose into 2-4 independent sub-questions covering different aspects.",
            "deep":   "Generate 3-5 queries exploring different perspectives, methodologies, or expert views.",
        }.get(query_type, "Generate 2-4 queries covering the topic.")

        gap_hint = f"\nKnown gaps to fill: {gaps}" if gaps else ""
        context = ""
        if results:
            # 压缩：只传摘要而非全文，避免上下文膨胀
            context = "\nCurrent coverage summary:\n" + _summarize(results)

        resp = self._llm.invoke([
            SystemMessage(content=(
                "You are a research planner.\n"
                f"Strategy: {strategy}\n"
                "Never repeat already-searched queries.\n"
                'Output ONLY valid JSON: {"queries": ["q1", "q2", ...]}\n'
                'If nothing new to search: {"queries": []}'
            )),
            HumanMessage(content=(
                f"Topic: {topic}\n"
                f"Query type: {query_type}\n"
                f"Already searched: {searched}"
                f"{gap_hint}"
                f"{context}"
            )),
        ])
        try:
            raw = resp.content.strip().strip("```json").strip("```").strip()
            return json.loads(raw).get("queries", [])
        except (json.JSONDecodeError, AttributeError):
            return [topic] if not searched else []

    def _evaluate_coverage(self, topic: str, results: dict[str, str]) -> dict:
        resp = self._llm.invoke([
            SystemMessage(content=(
                "You are a research evaluator.\n"
                "Output ONLY valid JSON:\n"
                '{"situation": "brief summary", "gaps": ["gap1", ...], "confidence": 0.0-1.0}\n'
                "confidence: 0.0=very incomplete, 1.0=fully covered"
            )),
            HumanMessage(content=(
                f"Topic: {topic}\n\n"
                f"Results:\n{_aggregate(results)[:4000]}"
            )),
        ])
        try:
            raw = resp.content.strip().strip("```json").strip("```").strip()
            return json.loads(raw)
        except (json.JSONDecodeError, AttributeError):
            return {"situation": "", "gaps": [], "confidence": 0.7}

    def _adapt(self, situation: dict, cycle: int, searched: list[str]) -> str:
        confidence = situation.get("confidence", 0.7)
        gaps = situation.get("gaps", [])

        # 强制终止：最后一轮 or 无新 gap（边际收益递减）
        if cycle >= self.MAX_CYCLES or not gaps:
            return "SYNTHESIZE"
        # 搜索量过多时及时止损
        if len(searched) >= 10:
            return "SYNTHESIZE"
        # 贝叶斯：高置信度直接综合
        if confidence >= 0.75:
            return "SYNTHESIZE"
        return "OBSERVE_MORE"

    def _synthesize(self, topic: str, results: dict[str, str], memory: dict, research_dir: Path) -> str:
        aggregated = _aggregate(results)
        resp = self._llm.invoke([
            SystemMessage(content=(
                "You are a research synthesizer.\n"
                "Write a concise markdown research report.\n"
                "Include: key findings, common themes, notable sources (URLs).\n"
                "Be factual and cite URLs where relevant."
            )),
            HumanMessage(content=f"Topic: {topic}\n\nSearch results:\n{aggregated}"),
        ])
        summary = resp.content.strip()

        slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", topic)[:40]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = research_dir / f"{slug}_{timestamp}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            f"# Research: {topic}\n\n"
            f"{summary}\n\n"
            f"---\n\n"
            f"## Research Memory\n\n```json\n{json.dumps(memory, ensure_ascii=False, indent=2)}\n```\n\n"
            f"---\n\n"
            f"## Raw Results\n\n{aggregated}"
        )
        return str(file_path)

    # ── 并行委派 ──────────────────────────────────────────────────────────────

    def _dispatch(
        self, queries: list[str], topic: str = "", difficulty: str = "medium"
    ) -> dict[str, str]:
        """每个 query 创建独立 SearchSubagent 实例（独立上下文），并行执行。"""
        results: dict[str, str] = {}

        def _run(q: str) -> tuple[str, str]:
            # 每次调用创建新实例，保证独立上下文；结果写入文件，返回路径
            agent = SearchSubagent(difficulty=difficulty)
            return q, agent.run(q, topic=topic, research_dir=self._research_dir)

        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            futures = {executor.submit(_run, q): q for q in queries}
            for future in as_completed(futures):
                q, result = future.result()
                results[q] = result
                logger.info("subagent done: %s", q[:60])

        return results


# ── helpers ───────────────────────────────────────────────────────────────────

def _aggregate(results: dict[str, str]) -> str:
    lines = []
    for i, (query, path_or_text) in enumerate(results.items(), 1):
        lines.append(f"## Query {i}: {query}")
        content = _read_result(path_or_text)
        lines.append(content)
        lines.append("")
    return "\n".join(lines).strip()


def _summarize(results: dict[str, str], max_chars: int = 3000) -> str:
    """压缩摘要：每条查询只保留前 N 字符，避免 evaluate_coverage 阶段上下文膨胀。"""
    lines = []
    per_query = max(300, max_chars // max(len(results), 1))
    for query, path_or_text in results.items():
        content = _read_result(path_or_text)
        lines.append(f"[{query}]: {content[:per_query]}")
    return "\n".join(lines)


def _read_result(path_or_text: str) -> str:
    """若值是存在的文件路径则读取文件，否则直接返回文本。"""
    p = Path(path_or_text)
    if p.exists():
        return p.read_text()
    return path_or_text
