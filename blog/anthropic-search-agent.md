---
title: "落地实现 Anthropic Multi-Agent Research System"
description: "从单 Agent 研究的三大痛点出发，深度解析 Anthropic 工程博客中的 Multi-Agent Research System 设计，并用 Python 完整实现：OODA 循环、并行 SearchSubagent、文件系统存储、CitationAgent 引用核查。"
image: "/images/blog/search-agent.jpg"
keywords:
  - Multi-Agent
  - Research System
  - OODA Loop
  - SearchSubagent
  - CitationAgent
  - Anthropic
  - LangChain
  - DuckDuckGo
tags:
  - Agent
  - Multi-Agent
  - Research
  - OODA
  - Python
author: "manus-learn"
date: "2026-02-27"
last_modified_at: "2026-02-27"
lang: "zh-CN"
audience: "开发者 / 对 AI Agent 感兴趣的工程师"
difficulty: "intermediate"
estimated_read_time: "18-22min"
---

# 落地实现 Anthropic Multi-Agent Research System

## 📍 阅读路径

根据你的背景，选择合适的切入点：

- 🧠 **先看理论** → [第一部分：为什么单 Agent 研究不够用](#part-1)
- ⚙️ **直接看架构** → [第二部分：三层架构设计](#part-2)
- 💻 **直接看代码** → [第三部分：完整实现](#part-3)

---

## 目录

### 第一部分：问题与解法 🧠
- [单 Agent 研究的三大痛点](#single-agent-problems)
- [Anthropic 的解决思路](#anthropic-solution)

### 第二部分：架构设计 ⚙️
- [两种循环：LeadAgent vs SubAgent](#two-loops)
- [三层拆分：LeadAgent / SearchSubagent / CitationAgent](#three-layers)
- [文件系统：解决传声筒效应](#filesystem)

### 第三部分：代码实现 💻
- [SearchSubagent：Tool-Calling 深挖循环](#subagent-ooda)
- [SearchLeadAgent：评估-分类-计划-执行](#lead-agent)
- [CitationAgent：内联引用插入](#citation-agent)
- [完整调用链](#full-chain)
- [代码结构总览](#code-structure)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

Anthropic 工程博客发布了一篇文章：[How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)。

文章描述了 Claude Research 功能背后的架构：一个 Lead Agent 规划研究流程，并行 spawn 多个 Search Agent 同时搜索，结果写入文件系统，最后由 CitationAgent 核查引用。

这篇文章把这套架构用 Python 完整实现出来，并作为独立模块集成到 AI Agent 项目中。

---

<a id="part-1"></a>
## 第一部分：问题与解法 🧠

<a id="single-agent-problems"></a>
### 单 Agent 研究的三大痛点

让 LLM 做研究，最直接的方式是：

```
用户: "帮我研究量子计算的最新进展"
        ↓
Agent
  → web_search("量子计算")
  → web_search("quantum computing 2025")
  → web_search("量子计算应用场景")
  → ... 串行执行，结果全部堆进 context
  → 综合回答
```

这个方式有三个核心问题：

**问题 1：Context 窗口过载**

每次搜索结果都直接进入 Agent 的 context，研究越深入，context 越臃肿。当 token 接近上限时，早期的搜索结果会被压缩甚至丢失，导致「遗忘」。

**问题 2：串行执行，速度慢**

搜索是 I/O 密集型操作，等待网络响应的时间远大于 LLM 思考时间。串行执行 5 个查询，耗时是并行的 5 倍。

**问题 3：缺乏深度迭代**

单 Agent 往往搜一次就综合，没有「搜到结果后发现新线索、继续深挖」的能力。人类研究员会根据初步结果调整搜索策略，单 Agent 做不到。

<a id="anthropic-solution"></a>
### Anthropic 的解决思路

Anthropic 的核心思路是：

> "an agent that plans a research process based on user queries, and then uses tools to **create parallel agents that search for information simultaneously**"

把一个大任务拆成三层：

```
SearchLeadAgent（规划 + 编排）
    ↓ 并行 spawn
SearchSubagent × N（独立上下文，各自搜透一条查询，写文件）
    ↓ 结果路径汇总
SearchLeadAgent（综合报告）→ CitationAgent（内联引用）
```

每一层解决一个具体问题：
- SearchLeadAgent 解决「搜什么、搜够了没有」的问题
- SearchSubagent 解决「怎么把一条查询搜透」的问题
- 文件系统解决「context 过载」的问题
- CitationAgent 解决「声明是否有来源支撑」的问题

---

<a id="part-2"></a>
## 第二部分：架构设计 ⚙️

<a id="two-loops"></a>
### 两种循环：LeadAgent vs SubAgent

这套系统有两个不同性质的循环，分别对应不同的决策模式：

**SearchSubagent — OODA 循环（微观，响应式）**

OODA 是军事决策模型，由美国空军上校 John Boyd 提出，适合「在不确定环境中持续迭代」的场景。SubAgent 面对的正是这种场景：搜索结果不可预测，需要根据每次结果动态调整。

| 阶段 | 在 SubAgent 中的作用 |
|------|---------------------|
| **Observe** | 并行执行当前批次查询 / 抓取 URL 全文 |
| **Orient** | LLM 评估结果质量，区分事实与推测，识别冲突 |
| **Decide** | DONE \| REFINE \| BROADEN \| FETCH |
| **Act** | 继续搜索 / 抓取 URL / 返回结果 |

**SearchLeadAgent — 评估-分类-计划-执行（宏观，主动式）**

LeadAgent 不是被动响应，而是主动规划。它在循环开始前先做两步预处理，再进入四步循环：

```
pre-loop:
  评估  → _probe()     快速探索信息版图
  分类  → _classify()  判断查询类型（direct / broad / deep）

loop (最多 4 轮):
  计划  → _plan_queries()      按类型生成查询，针对 gaps 补搜
  执行  → _dispatch()          并行 spawn SearchSubagent
  监控  → _evaluate_coverage() 评估覆盖度，识别信息缺口
  适应  → _adapt()             贝叶斯更新：继续 or 止损综合
```

**Decide 阶段不调 LLM**，直接用规则判断：

```python
def _adapt(self, situation: dict, cycle: int, searched: list[str]) -> str:
    confidence = situation.get("confidence", 0.7)
    gaps = situation.get("gaps", [])
    if cycle >= self.MAX_CYCLES or not gaps:
        return "SYNTHESIZE"
    if len(searched) >= 10:
        return "SYNTHESIZE"
    if confidence >= 0.75:
        return "SYNTHESIZE"
    return "OBSERVE_MORE"
```

原因：`_adapt` 的输入（confidence 数值 + gaps 列表）已经是结构化数据，规则判断比 LLM 更快、更稳定、成本更低。

<a id="three-layers"></a>
### 三层拆分

| 维度 | SearchLeadAgent | SearchSubagent | CitationAgent |
|------|-----------------|----------------|---------------|
| **职责** | 研究规划 + 并行编排 + 触发引用 | 执行单条查询，搜透为止 | 内联引用插入 |
| **循环模式** | 评估-分类-计划-执行（最多 4 轮） | OODA（budget 由难度决定） | 单次执行 |
| **LLM 调用** | classify / plan / evaluate | evaluate（每轮） | extract_citations |
| **输出** | 最终报告文件路径 | 原始结果文件路径 | 修改报告文件（内联标记） |
| **Context** | 独立，仅含研究状态 + 文件路径 | 独立，仅含单条查询结果 | 独立，仅含报告内容 |

三个组件都是独立的 Python 类，但 CitationAgent 由 SearchLeadAgent 在内部自动调用，调用方只需调用 `SearchLeadAgent.run(topic)` 即可得到完整的研究报告路径。

<a id="filesystem"></a>
### 文件系统：解决传声筒效应

Anthropic 文章中特别提到 **传声筒效应（Telephone Effect）**：在多层 Agent 传递信息时，每次传递都会消耗大量 token，并且 LLM 会自动摘要导致细节丢失。

**解决方案：两级写文件，只传路径**

```
SubAgent 完成搜索
  → 写入 scripts/research/sub_{query}_{timestamp}.md
  → 返回文件路径给 LeadAgent

LeadAgent 收集所有路径
  → all_results = {"量子计算 2025": "scripts/research/sub_量子计算_2025_....md", ...}
  → 内存里只有路径，不堆原始文本

LeadAgent 需要评估时
  → _read_result(path) 按需读取文件内容
  → 读完即丢，不常驻内存

LeadAgent 综合报告
  → 写入 scripts/research/{topic}_{timestamp}.md
  → 返回路径给调用方
```

`_read_result` 的实现很简单，但作用关键：

```python
def _read_result(path_or_text: str) -> str:
    p = Path(path_or_text)
    if p.exists():
        return p.read_text()
    return path_or_text  # 兜底：直接返回文本（standalone 模式）
```

调用方收到的是一个轻量级路径字符串，而不是几千字的搜索结果。需要时才读取文件，不需要时不占 token。

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="subagent-ooda"></a>
### SearchSubagent：Tool-Calling 深挖循环

SearchSubagent 不是简单的「搜一次返回」，它通过 tool-calling 循环自主决定何时搜索、何时抓取全文。

**两个工具**

```python
from backend.app.tools.search_tool import web_search
from backend.app.tools.fetch_tool import fetch_url

TOOLS = [web_search, fetch_url]
```

`web_search` 返回 DuckDuckGo 摘要列表，`fetch_url` 抓取 URL 完整页面文本。两者都是标准 `@tool`，封装在 `tools/` 层，可独立复用。

**动态研究预算**

```python
BUDGET = {"simple": 4, "medium": 5, "hard": 10, "extreme": 15}
MAX_TOOL_CALLS = 20   # 硬限制
```

迭代轮数由 LeadAgent 在 dispatch 时根据查询类型传入，`MAX_TOOL_CALLS` 是兜底硬限制。

**Tool-Calling 循环**

```python
def __init__(self, difficulty: str = "medium"):
    self._llm = get_llm().bind_tools(TOOLS)
    self._tools_map = {t.name: t for t in TOOLS}
    self._max_iter = BUDGET.get(difficulty, BUDGET["medium"])
    self._tool_calls = 0

def run(self, query: str, topic: str = "", research_dir: Path | None = None) -> str:
    messages = [SystemMessage(content=system), HumanMessage(content=f"Research: {query}")]
    resp = None

    for i in range(self._max_iter):
        if self._tool_calls >= MAX_TOOL_CALLS:
            break

        resp = self._llm.invoke(messages)
        messages.append(resp)

        if not resp.tool_calls:
            break   # LLM 认为信息已充足，给出最终答案

        for tc in resp.tool_calls:
            if self._tool_calls >= MAX_TOOL_CALLS:
                break
            self._tool_calls += 1
            result = self._tools_map[tc["name"]].invoke(tc["args"])
            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    # 预算耗尽时补一次 final summary
    if resp is None or resp.tool_calls:
        resp = get_llm().invoke(messages + [HumanMessage(content="Summarize all findings.")])

    results_text = resp.content
    if research_dir is not None:
        return _write_subagent_results(query, results_text, research_dir)
    return results_text
```

LLM 自主决定调用哪个工具、调用几次。需要摘要时用 `web_search`，需要深读某个页面时用 `fetch_url`。预算耗尽后强制触发一次 summary，保证始终有输出。

每个 SubAgent 实例独立，上下文互不干扰。完成后写入 `sub_{slug}_{timestamp}.md`，返回路径。

<a id="lead-agent"></a>
### SearchLeadAgent：评估-分类-计划-执行

LeadAgent 在进入主循环前，先做两步预处理：

**Pre-loop：探索 + 分类**

```python
def run(self, topic: str, research_dir: Path | None = None) -> str:
    _research_dir = research_dir or DEFAULT_RESEARCH_DIR
    self._research_dir = _research_dir   # 供 _dispatch 传给 SubAgent

    # 1. 探索：快速搜索，只取标题+URL列表，理解信息版图
    probe_hint = self._probe(topic)

    # 2. 分类：判断查询类型
    query_type = self._classify(topic, probe_hint)
    # → "direct" | "broad" | "deep"
```

`_classify` 根据 probe 结果让 LLM 判断查询类型，不同类型对应不同的 SubAgent 数量和难度：

```python
_SUBAGENT_COUNT = {"direct": 1, "broad": 3, "deep": 5}
_DIFFICULTY     = {"direct": "simple", "broad": "medium", "deep": "hard"}
```

**主循环：四步**

```python
for cycle in range(1, self.MAX_CYCLES + 1):
    # 计划：生成本轮查询，针对 gaps 补搜
    gaps = memory["cycles"][-1]["gaps"] if memory["cycles"] else []
    queries = self._plan_queries(topic, memory["searched"], all_results, gaps, query_type)

    # 执行：并行 dispatch，每个 SubAgent 写文件返回路径
    batch = self._dispatch(new_queries, topic=topic, difficulty=difficulty)
    all_results.update(batch)   # {query: file_path}

    # 监控：评估覆盖度
    situation = self._evaluate_coverage(topic, all_results)
    confidence = situation.get("confidence", 0.5)

    # 适应：决定继续还是综合
    if self._adapt(situation, cycle, memory["searched"]) == "SYNTHESIZE":
        break
```

`all_results` 里存的是文件路径，不是原始文本。`_evaluate_coverage` 和 `_plan_queries` 需要读内容时，通过 `_read_result()` 按需读取：

```python
def _aggregate(results: dict[str, str]) -> str:
    for query, path_or_text in results.items():
        content = _read_result(path_or_text)   # 按需读文件
        lines.append(content)

def _summarize(results: dict[str, str], max_chars: int = 3000) -> str:
    per_query = max(300, max_chars // max(len(results), 1))
    for query, path_or_text in results.items():
        content = _read_result(path_or_text)
        lines.append(f"[{query}]: {content[:per_query]}")  # 截断压缩
```

`_summarize` 用于 `_plan_queries` 的上下文（轻量），`_aggregate` 用于 `_evaluate_coverage` 和 `_synthesize`（完整）。

**dispatch：每次新实例**

```python
def _dispatch(self, queries, topic="", difficulty="medium") -> dict[str, str]:
    def _run(q: str) -> tuple[str, str]:
        agent = SearchSubagent(difficulty=difficulty)   # 每次新实例，独立上下文
        return q, agent.run(q, topic=topic, research_dir=self._research_dir)

    with ThreadPoolExecutor(max_workers=len(queries)) as executor:
        futures = {executor.submit(_run, q): q for q in queries}
        for future in as_completed(futures):
            q, result = future.result()
            results[q] = result   # result 是文件路径
```

N 个查询同时执行，速度提升 N 倍。`with ThreadPoolExecutor` 退出时自动 `shutdown(wait=True)`，保证所有 SubAgent 都完成后才继续。

<a id="citation-agent"></a>
### CitationAgent：内联引用插入

研究报告生成后，CitationAgent 在 summary 中精确插入 `[^N]` 引用标记。**它由 SearchLeadAgent 在 `_synthesize` 之后自动调用，不需要外部手动触发。**

核心约束：**文本内容 100% 不变，唯一权限是插入引用标记**。这是为了支持后续系统的 Diffing 校验——去掉标记后，文本必须与原文完全一致，否则判定篡改。

**流程：**

```
1. 读取报告，按 "## Raw Results" 分离 summary 和 raw results
2. LLM 先推理，再识别 (snippet, url) 对
3. 在 summary 中精确插入 [^N] 标记（句末/子句末）
4. 一致性校验：strip 标记后 == 原 summary
5. 追加 ## References 区块，写回文件
```

**LLM 提取引用（Careful Reasoning）：**

```python
SystemMessage(content=(
    "You are a citation extractor.\n"
    "First reason about which claims need citations, then output a JSON decision.\n"
    "Rules:\n"
    "- Only cite factual claims (numbers, dates, specific events), NOT common knowledge\n"
    "- snippet must be an EXACT substring from the summary\n"
    "- snippet should be a complete semantic unit\n"
    "- Place the citation marker at the END of a sentence or clause, never mid-phrase\n"
    "- Each URL should appear at most once\n"
    'Output ONLY valid JSON: {"reasoning": "...", "citations": [{"snippet": "...", "url": "..."}]}'
))
```

**一致性校验（防篡改）：**

```python
stripped = re.sub(r"\[\^\d+\]", "", annotated_summary)
if stripped != summary_part:
    logger.warning("CitationAgent: consistency check failed, reverting")
    return "consistency check failed"   # 不写回文件
```

**输出格式：**

```markdown
研究报告正文...量子计算领域在 2025 年取得重大突破[^1]，IBM 发布了 1000 量子比特处理器[^2]。

---

## References

[^1]: https://example.com/quantum-2025
[^2]: https://research.ibm.com/...
```

<a id="full-chain"></a>
### 完整调用链

```
输入: topic = "量子计算最新进展"
        ↓
SearchLeadAgent.run(topic)

  pre-loop:
    _probe()     → 快速搜索，了解信息版图
    _classify()  → "deep"（单一话题，需多视角深挖）
    → max_subagents=5, difficulty="hard", budget=10

  cycle 1:
    _plan_queries() → ["量子计算 2025", "quantum supremacy", "量子纠错", "量子计算应用"]
    _dispatch()     → 并行 spawn 4 个 SearchSubagent（各自 tool-calling，写文件）
                        ├── sub_量子计算_2025_....md
                        ├── sub_quantum_supremacy_....md
                        ├── sub_量子纠错_....md
                        └── sub_量子计算应用_....md
    all_results = {query: file_path, ...}   ← 只存路径

    _evaluate_coverage() → confidence=0.55, gaps=["商业化进展", "投资动态"]
    _adapt()             → OBSERVE_MORE

  cycle 2:
    _plan_queries() → ["量子计算商业化 2025", "量子计算投资"]（针对 gaps）
    _dispatch()     → 并行 spawn 2 个 SubAgent
    _evaluate_coverage() → confidence=0.82
    _adapt()             → SYNTHESIZE（confidence >= 0.75）

  _synthesize() → 读取所有文件 → LLM 综合
               → 写入 scripts/research/量子计算_20260227_143022.md

  CitationAgent.run(path)  ← 内部自动调用
    → 读报告 → LLM 推理 → 插入 [^N] → 一致性校验 → 写回

  返回: "scripts/research/量子计算_20260227_143022.md"
```

调用方只需一行：

```python
path = SearchLeadAgent().run("量子计算最新进展")
# 或通过 @tool 包装
path = search_lead.invoke({"topic": "量子计算最新进展"})
```

<a id="code-structure"></a>
### 代码结构总览

```
backend/app/
├── search/
│   ├── __init__.py              # 导出 DuckDuckGoSearch, WebFetch
│   ├── duckduckgo.py            # 搜索引擎封装（无 LLM，可独立测试）
│   └── fetch.py                 # URL 抓取封装（无 LLM，可独立测试）
│
├── search_agent/
│   ├── __init__.py              # 导出三个 Agent 类
│   ├── search_subagent.py       # Tool-calling 深挖循环，写 sub_*.md，返回路径
│   ├── lead_agent.py            # 评估-分类-计划-执行，并行 dispatch，写最终报告
│   └── citation_agent.py        # 内联 [^N] 引用插入，一致性校验
│
└── tools/
    ├── search_tool.py           # web_search → DuckDuckGoSearch（单次搜索）
    ├── fetch_tool.py            # fetch_url → WebFetch（URL 全文抓取）
    └── search_agent_tool.py     # search_lead → SearchLeadAgent（完整研究流水线）
```

分层原则：
- `search/` 是基础设施层，无 LLM，可独立测试
- `search_agent/` 是业务逻辑层，三个 Agent 类在这里
- `tools/` 是接口层，只做 `@tool` 装饰和参数转发

`web_search`、`fetch_url`、`search_lead` 是三个不同粒度的工具：前两者是原子操作，后者是完整研究流水线。换搜索引擎只改 `search/`，换 Agent 策略只改 `search_agent/`，上层调用方感知不到变化。

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: LeadAgent 为什么不用 OODA？SubAgent 为什么也不用了？**

OODA 是响应式模型，适合「看到结果再决定下一步」的场景。LeadAgent 的工作是主动规划：先探索信息版图、判断查询类型、制定策略，再执行，是「评估-分类-计划-执行」的主动式循环。SubAgent 之前用手动 OODA 循环（`_evaluate` 输出 DONE/REFINE/BROADEN/FETCH），现在改为标准 tool-calling 循环——LLM 直接决定调用 `web_search` 还是 `fetch_url`，逻辑更简洁，也更符合 LangChain 的工具调用范式。

**Q: 为什么用 DuckDuckGo 而不是 Tavily 或 SerpAPI？**

DuckDuckGo 不需要 API Key，`duckduckgo-search` 库开箱即用，适合学习和原型阶段。生产环境可以换成 Tavily（专为 AI 设计，结果质量更好）或 SerpAPI（更稳定），只需替换 `search/duckduckgo.py` 即可。

**Q: SubAgent 怎么决定搜多少次？**

LLM 通过 tool-calling 自主决定。每轮 LLM 可以调用 `web_search`（搜索）或 `fetch_url`（抓取全文），直到它认为信息充足为止（不再输出 tool_calls）。预算上限由 `BUDGET` 控制（`hard` 模式最多 10 轮），`MAX_TOOL_CALLS = 20` 是硬限制兜底。

**Q: CitationAgent 为什么不作为独立工具暴露？**

引用核查是研究流程的最后一步，和报告生成强耦合。把它内置在 SearchLeadAgent 里，保证每次研究都自动完成核查，不会被调用方遗漏。如果需要对已有报告单独核查，可以直接实例化 `CitationAgent` 调用。

**Q: 文件系统存储会不会有并发问题？**

SubAgent 用 `sub_{slug}_{timestamp}_{microseconds}` 命名文件，时间戳精确到微秒，并发冲突概率极低。LeadAgent 的最终报告同理。

**Q: tool-calling 最多 10 轮（hard），会不会太多？**

有硬限制兜底：`MAX_TOOL_CALLS = 20`。无论 budget 设多少，超过硬限制就停止。实际上大多数查询在 3-5 次工具调用内 LLM 就会停止输出 tool_calls，budget 是上限而不是固定次数。

---

## 📝 结语

这套架构的核心思想：

> **把研究过程的复杂性封装在独立的 Agent 层，调用方只看结果，不看过程。**

五个设计决策，每一个都对应一个具体的工程痛点：

| 设计决策 | 解决的问题 |
|---------|-----------|
| SubAgent Tool-Calling 循环 | 单次搜索不精准，LLM 自主决定搜索次数和工具选择 |
| LeadAgent 评估-分类-计划-执行 | 不同查询类型需要不同策略 |
| 两级并行（LeadAgent + SubAgent 内部） | 串行执行速度慢 |
| 两级文件系统（SubAgent + LeadAgent 都写文件） | Context 过载，传声筒效应 |
| CitationAgent 内联引用 + 一致性校验 | 声明无来源，报告不可信 |


