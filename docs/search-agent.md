# 落地实现 Anthropic Multi-Agent Research System

> 基于 [How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system) 的工程实践

---

## 一、问题背景：单 Agent 研究的局限

在没有 multi-agent 架构之前，让 LLM 做研究的方式是这样的：

```
用户: "帮我研究量子计算的最新进展"
        ↓
主 Agent
  → web_search("量子计算")
  → web_search("quantum computing 2024")
  → web_search("量子计算应用场景")
  → ... 串行执行，结果全部堆进 context
  → 综合回答
```

这个方式有三个核心问题：

**问题 1：Context 窗口过载**
每次搜索结果都直接进入主 Agent 的 context，研究越深入，context 越臃肿。当 token 接近上限时，早期的搜索结果会被压缩甚至丢失，导致"遗忘"。

**问题 2：串行执行，速度慢**
搜索是 I/O 密集型操作，等待网络响应的时间远大于 LLM 思考时间。串行执行 5 个查询，耗时是并行的 5 倍。Anthropic 的文章提到，这会让研究时间从分钟级变成小时级。

**问题 3：缺乏深度迭代**
单 Agent 往往搜一次就综合，没有"搜到结果后发现新线索、继续深挖"的能力。人类研究员会根据初步结果调整搜索策略，单 Agent 做不到。

---

## 二、Anthropic 的解决思路

Anthropic 在其工程博客中描述了他们为 Claude Research 功能构建的 multi-agent 系统，核心思路是：

> "an agent that plans a research process based on user queries, and then uses tools to **create parallel agents that search for information simultaneously**"

本质是把一个大任务拆成三层：

```
Lead Agent（规划 + 编排）
    ↓ 并行 spawn
Search Agent × N（独立上下文，各自搜索）
    ↓ 结果写文件
Lead Agent（综合 + 输出引用）
```

每一层解决一个具体问题：
- Lead Agent 解决"搜什么"的问题
- Search Agent 解决"怎么搜透"的问题
- 文件系统解决"context 过载"的问题

---

## 三、OODA 循环：让 Agent 像人一样思考

OODA（Observe-Orient-Decide-Act）是军事决策模型，被引入 AI Agent 设计后，解决的是"Agent 如何在不确定环境中持续迭代"的问题。

### SearchLeadAgent 的 OODA

```
┌─────────────────────────────────────────────────────┐
│  cycle 1                                            │
│                                                     │
│  Observe  → LLM 拆解 topic → 3-5 个宽泛子查询        │
│             并行 spawn SearchSubagent × N            │
│                                                     │
│  Orient   → LLM 评估覆盖度                           │
│             {"confidence": 0.55, "gaps": ["价格趋势"]}│
│                                                     │
│  Decide   → confidence < 0.6 → OBSERVE_MORE         │
│                                                     │
│  Act      → 继续下一轮（gaps 喂给下轮 Observe）        │
└─────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────┐
│  cycle 2                                            │
│                                                     │
│  Observe  → 针对 gaps 生成补充查询                    │
│  Orient   → confidence = 0.8                        │
│  Decide   → SYNTHESIZE                              │
│  Act      → 写报告 → 返回文件路径 ✅                  │
└─────────────────────────────────────────────────────┘
```

OODA 的关键价值在于 **Orient 阶段**：Agent 不是机械执行，而是在每轮结束后评估"我现在知道什么、还缺什么"，然后决定下一步。这模拟了人类研究员的思维方式。


---

## 四、三层架构：主 Agent vs SearchLeadAgent vs SearchSubagent

这是本次实现最核心的设计决策，三层各司其职：

### 对比表

| 维度 | 主 Agent | SearchLeadAgent | SearchSubagent |
|------|----------|-----------------|----------------|
| **职责** | 理解用户意图，协调全局 | 研究规划 + 并行编排 | 执行单条查询 |
| **LLM** | ✅ 有 | ✅ 有 | ✅ 有（refine loop）|
| **工具** | 全部工具 | 无外部工具 | DuckDuckGoSearch |
| **Context** | 完整对话历史 | 独立，仅含研究状态 | 独立，仅含单条查询 |
| **循环** | ReAct loop | OODA（最多4轮） | refine loop（最多3轮）|
| **输出** | 直接回复用户 | 文件路径 | 搜索结果字符串 |
| **生命周期** | 持续整个会话 | 一次研究任务 | 一条查询 |

### 为什么要三层，而不是两层？

**如果只有主 Agent + SearchSubagent：**
```
主 Agent 需要自己拆解查询 → 主 Agent 需要自己评估覆盖度
→ 主 Agent context 被研究过程污染
→ 主 Agent 无法专注用户的其他任务
```

**三层的好处：**
```
主 Agent 只说"研究X" → SearchLeadAgent 全权负责研究过程
→ 主 Agent context 只收到一个文件路径
→ 主 Agent 可以同时处理其他任务
```

这是 Anthropic 文章强调的 **"独立上下文窗口"** 设计原则的直接体现。

---

## 五、文件系统：解决传声筒效应

Anthropic 文章中特别提到一个问题：**传声筒效应（Telephone Effect）**。

在多层 Agent 传递信息时，每次传递都会：
1. 消耗大量 token（把完整结果塞进消息）
2. 丢失细节（LLM 会自动摘要，导致信息损失）
3. 污染上层 Agent 的 context

**解决方案：文件系统作为共享存储**

```python
# SearchLeadAgent 不返回内容，返回路径
def _synthesize(self, topic, results, memory) -> str:
    file_path = RESEARCH_DIR / f"{slug}_{timestamp}.md"
    file_path.write_text(full_report)
    return str(file_path)  # ← 只返回路径
```

```
SearchLeadAgent → 写入 scripts/research/量子计算_20260227.md
        ↓ 返回路径
主 Agent 收到 "scripts/research/量子计算_20260227.md"
        ↓ 按需读取
read_file("scripts/research/量子计算_20260227.md")
```

主 Agent 的 context 里只有一个文件路径，而不是几千字的搜索结果。需要时才读，不需要时不占 token。


---

## 六、SearchSubagent 的 Refine Loop

SearchSubagent 不是简单的"搜一次返回"，它有自己的迭代能力：

```python
for i in range(1, MAX_ITERATIONS + 1):
    # 执行搜索
    results = self._ddg.search(current_query)

    # LLM 评估：够了还是需要精炼？
    decision = self._evaluate(original_query, current_query, results, i)

    if decision["status"] == "DONE":
        break
    # REFINE：用更精确的查询继续
    current_query = decision["next_query"]
```

**为什么 SearchSubagent 需要 refine loop？**

第一次搜索往往不精准：
```
查询: "量子计算"
结果: 大量科普文章，缺乏最新进展

LLM 评估: REFINE
next_query: "quantum computing breakthrough 2025 IBM Google"

结果: 具体的技术突破新闻 ✅
```

这对应 Anthropic 文章中的 **"Start Wide, then Narrow"** 策略：先用宽泛查询了解信息版图，再用精确查询深挖细节。

**与 OODA 的区别：**
- OODA 是宏观循环，决定"研究哪些方向"
- Refine Loop 是微观循环，决定"这个方向怎么搜透"

两者嵌套，形成两级迭代：

```
OODA cycle 1
  └── Observe: 并行 spawn 4 个 SearchSubagent
        ├── SubAgent A: refine loop × 2 轮
        ├── SubAgent B: refine loop × 1 轮（第一次就够了）
        ├── SubAgent C: refine loop × 3 轮
        └── SubAgent D: refine loop × 2 轮
OODA cycle 2（如果 confidence 不足）
  └── 针对 gaps 再 spawn 2 个 SubAgent
        ...
```


---

## 七、CitationAgent：可信度保障

Anthropic 文章提到研究系统的最后一步是引用核查：

> "a specialized CitationAgent that verifies every claim can be traced back to a specific source"

本实现中 `citation_verify` tool 做的事：

```
读取报告文件
    ↓
LLM 逐条核查：每个关键声明 → 能否在 Raw Results 中找到对应 URL？
    ↓
输出：
- ✅ 量子计算机在2024年实现了1000量子比特 → https://...
- ⚠️ 量子计算将在5年内取代传统计算机 → unverified
    ↓
追加写入原报告文件
```

**为什么需要独立的 CitationAgent？**

LLM 有"幻觉"问题，在综合大量搜索结果时可能：
- 混淆不同来源的信息
- 生成听起来合理但无法溯源的声明
- 夸大或曲解原始数据

CitationAgent 作为独立的核查层，强制每条声明都要有 URL 支撑，是对 LLM 输出可信度的系统性保障。

---

## 八、完整调用链

```
用户: "研究量子计算2025年最新进展"
        ↓
主 Agent
  → search_lead("量子计算2025年最新进展")
        ↓
  SearchLeadAgent.run(topic)
  │
  ├── OODA cycle 1
  │   Observe: LLM 拆解
  │     → ["quantum computing 2025", "量子计算突破", "IBM Google量子", "量子纠错进展"]
  │   并行 spawn SearchSubagent × 4
  │     ├── SubAgent: "quantum computing 2025" → refine → 结果A
  │     ├── SubAgent: "量子计算突破" → DONE → 结果B
  │     ├── SubAgent: "IBM Google量子" → refine → 结果C
  │     └── SubAgent: "量子纠错进展" → refine → 结果D
  │   Orient: confidence=0.75 ✅
  │   Decide: SYNTHESIZE
  │   Act: LLM 综合 → 写入 scripts/research/量子计算_20260227_143022.md
  │
  └── 返回 "scripts/research/量子计算_20260227_143022.md"
        ↓
主 Agent 收到路径
  → read_file("scripts/research/量子计算_20260227_143022.md")
  → citation_verify("scripts/research/量子计算_20260227_143022.md")
  → 向用户汇报结果
```

---

## 九、解决了什么问题，带来了什么好处

| 问题 | 解决方案 | 效果 |
|------|----------|------|
| Context 过载 | 文件系统存储，主 Agent 只收路径 | 主 Agent context 保持轻量 |
| 串行搜索慢 | ThreadPoolExecutor 并行 spawn | N 个查询同时执行，速度提升 N 倍 |
| 搜索不深入 | SearchSubagent refine loop | 自动从宽泛到精确，搜透单个方向 |
| 研究方向不全 | OODA Orient 识别 gaps | 多轮补搜，覆盖度可量化（confidence） |
| 信息可信度低 | CitationAgent 核查 | 每条声明强制溯源到 URL |
| 主 Agent 被研究过程污染 | SearchLeadAgent 独立上下文 | 主 Agent 专注用户任务 |

---

## 十、与 Anthropic 原文的对应关系

| Anthropic 文章描述 | 本实现对应 |
|-------------------|-----------|
| Lead Agent 规划研究流程 | `SearchLeadAgent._observe()` |
| 并行创建多个 Search Agent | `SearchLeadAgent._parallel_search()` |
| 独立上下文窗口 | 每个 `SearchSubagent` 实例独立 |
| Start Wide, then Narrow | `SearchSubagent` refine loop |
| Interleaved Thinking | OODA Orient + Decide 阶段 |
| 文件系统存储，轻量级引用 | `_synthesize()` 写文件，返回路径 |
| CitationAgent 引用核查 | `citation_verify` tool |
| 错误处理与自我纠偏 | refine loop fallback + OODA MAX_CYCLES |

---

## 十一、代码结构总览

```
backend/app/
├── search/
│   └── duckduckgo.py          # 搜索引擎封装（无 LLM）
│
├── search_agent/              # 独立研究模块
│   ├── search_subagent.py     # 单条查询 refine loop
│   ├── lead_agent.py          # OODA 编排 + 并行执行
│   └── __init__.py
│
└── tools/                     # 暴露给主 Agent 的工具
    ├── search_tool.py         # web_search（单次搜索）
    ├── search_lead_tool.py    # search_lead（复杂研究）
    └── citation_tool.py       # citation_verify（引用核查）
```

**设计原则：**
- `search/` 是基础层，只封装搜索引擎，无业务逻辑
- `search_agent/` 是业务层，独立自治，不依赖主 Agent 框架
- `tools/` 是接口层，通过 `@tool` 装饰器暴露给 LLM，自动被 `auto_discover` 注册

这种分层让 `search_agent/` 可以独立测试、独立替换（比如把 DuckDuckGo 换成 Tavily），而不影响主 Agent 的任何逻辑。

