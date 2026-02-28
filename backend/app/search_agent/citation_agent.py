from __future__ import annotations
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from backend.app.llm import get_llm
from backend.app.tools.base import _safe_path

logger = logging.getLogger(__name__)

G = "\033[90m"
R = "\033[0m"


class CitationAgent:
    """
    引用插入 agent。

    核心约束：
    - 文本内容 100% 不变，唯一权限是插入引用标记 [^N]
    - 严禁添加或删除任何空格
    - 只引关键事实，不引常识
    - 使用完整语义单元，避免碎片化
    - 完成后做一致性校验（去掉标记后与原文对比）

    流程：
    1. 读取报告，分离 summary 和 raw results
    2. LLM 识别 (claim_snippet, url) 对
    3. 在 summary 中精确插入 [^N] 标记
    4. 追加 ## References 区块
    5. 一致性校验
    6. 写回文件
    """

    def __init__(self):
        self._llm = get_llm()

    def run(self, report_path: str) -> str:
        print(f"{G}📎 [CitationAgent] start: {report_path}{R}")

        try:
            fp = _safe_path(report_path)
        except ValueError as e:
            return f"Error: {e}"
        if not fp.exists():
            return f"Error: file not found: {report_path}"

        original = fp.read_text()

        # 分离 summary（## Raw Results 之前）和 raw results
        summary_part, raw_part = _split_report(original)
        if not raw_part:
            print(f"{G}📎 [CitationAgent] no raw results section, skip{R}")
            return "skipped: no raw results"

        # LLM 识别需要引用的 (claim, url) 对
        citations = self._extract_citations(summary_part, raw_part)
        if not citations:
            print(f"{G}📎 [CitationAgent] no citations found{R}")
            return "no citations"

        # 在 summary 中插入 [^N] 标记
        annotated_summary, refs = _insert_markers(summary_part, citations)

        # 一致性校验：去掉标记后应与原 summary 完全一致
        stripped = re.sub(r"\[\^\d+\]", "", annotated_summary)
        if stripped != summary_part:
            logger.warning("CitationAgent: consistency check failed, reverting")
            print(f"{G}📎 [CitationAgent] ⚠️ consistency check failed, skip{R}")
            return "consistency check failed"

        # 构建最终文件内容：annotated summary + 原始 raw 部分 + References
        refs_block = _build_refs_block(refs)
        final = annotated_summary + raw_part + refs_block

        fp.write_text(final)
        print(f"{G}📎 [CitationAgent] ✅ inserted {len(refs)} citations{R}")
        return f"inserted {len(refs)} citations"

    # ── LLM 提取引用对 ────────────────────────────────────────────────────────

    def _extract_citations(self, summary: str, raw: str) -> list[dict]:
        """
        让 LLM 从 summary 中识别关键事实声明，并匹配 raw results 中的 URL。

        返回：[{"snippet": "原文片段（精确）", "url": "https://..."}, ...]
        """
        resp = self._llm.invoke([
            SystemMessage(content=(
                "You are a citation extractor.\n"
                "First reason about which claims need citations, then output a JSON decision.\n"
                "Given a research summary and raw search results, identify key factual claims "
                "in the summary that can be traced to a specific URL in the raw results.\n\n"
                "Rules:\n"
                "- Only cite factual claims (numbers, dates, specific events), NOT common knowledge\n"
                "- snippet must be an EXACT substring from the summary (copy-paste, no paraphrasing)\n"
                "- snippet should be a complete semantic unit (full clause or sentence fragment)\n"
                "- Place the citation marker at the END of a sentence or clause, never mid-phrase\n"
                "- Each URL should appear at most once\n"
                "- If a claim cannot be traced to any URL, skip it\n\n"
                "Output ONLY valid JSON:\n"
                '{"reasoning": "brief analysis of which claims need citations", '
                '"citations": [{"snippet": "exact text from summary", "url": "https://..."}, ...]}\n'
                "If no citations found: {\"reasoning\": \"...\", \"citations\": []}"
            )),
            HumanMessage(content=(
                f"## Summary\n{summary}\n\n"
                f"## Raw Results (source URLs)\n{raw[:5000]}"
            )),
        ])
        try:
            raw_json = resp.content.strip().strip("```json").strip("```").strip()
            return json.loads(raw_json).get("citations", [])
        except (json.JSONDecodeError, AttributeError):
            return []


# ── helpers ───────────────────────────────────────────────────────────────────

def _split_report(content: str) -> tuple[str, str]:
    """将报告分为 summary 部分和 raw results 部分。"""
    marker = "\n## Raw Results\n"
    idx = content.find(marker)
    if idx == -1:
        return content, ""
    return content[:idx + 1], content[idx:]


def _insert_markers(summary: str, citations: list[dict]) -> tuple[str, list[tuple[int, str]]]:
    """
    在 summary 中精确插入 [^N] 标记。

    - 只在 snippet 首次出现位置插入（避免重复）
    - 标记插入在 snippet 末尾之后
    - 返回 (annotated_summary, [(ref_num, url), ...])
    """
    result = summary
    refs: list[tuple[int, str]] = []
    used_urls: set[str] = set()
    offset = 0  # 因为插入标记后位置会偏移

    for item in citations:
        snippet: str = item.get("snippet", "").strip()
        url: str = item.get("url", "").strip()

        if not snippet or not url or url in used_urls:
            continue

        # 在当前 result 中查找 snippet
        pos = result.find(snippet, offset)
        if pos == -1:
            continue

        ref_num = len(refs) + 1
        marker = f"[^{ref_num}]"
        insert_at = pos + len(snippet)

        result = result[:insert_at] + marker + result[insert_at:]
        offset = insert_at + len(marker)  # 下次搜索从这里开始，避免重叠

        refs.append((ref_num, url))
        used_urls.add(url)

    return result, refs


def _build_refs_block(refs: list[tuple[int, str]]) -> str:
    """构建 ## References 区块。"""
    if not refs:
        return ""
    lines = ["\n\n---\n\n## References\n"]
    for num, url in refs:
        lines.append(f"[^{num}]: {url}")
    return "\n".join(lines) + "\n"
