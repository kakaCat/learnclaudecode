---
title: "Unix 配置哲学 × AI Agent：用纯文本文件教会 Agent 任何技能"
description: "Unix 用 .bashrc、.vimrc 这样的纯文本文件配置程序行为，AI Agent 也可以。本文解析 Skill Loading 机制——如何用一个 .md 文件，让 Agent 在需要时「按需加载」专业知识，而不是把所有东西塞进 System Prompt。"
image: "/images/blog/skill-loading.jpg"
keywords:
  - Claude Code
  - AI Agent
  - Skill Loading
  - Unix Philosophy
  - System Prompt
  - Anthropic
tags:
  - Agent
  - Skills
  - Unix
  - Implementation
author: "manus-learn"
date: "2026-02-23"
last_modified_at: "2026-02-23"
lang: "zh-CN"
audience: "开发者 / 对 AI Agent 感兴趣的工程师"
difficulty: "intermediate"
estimated_read_time: "12-15min"
topics:
  - Unix Philosophy
  - Skill Loading
  - Two-layer Injection
  - Agent Knowledge Management
series: "从零构建 Claude Code"
series_order: 5
---

# 构建mini Claude Code：05 - 用纯文本文件教会 Agent 任何技能

## 📍 导航指南

这是「从零构建 Claude Code」系列的第四篇。根据你的背景，选择合适的阅读路径：

- 🧠 **理论派？** → [第一部分：Unix 配置哲学](#part-1) - 理解纯文本配置如何映射到 Agent 知识
- ⚙️ **实践派？** → [第二部分：两层注入机制](#part-2) - 掌握按需加载技能的核心设计
- 💻 **代码派？** → [第三部分：代码实现](#part-3) - 直接看 SkillLoader 完整实现

---

## 目录

### 第一部分：理论基础 🧠
- [Unix 配置哲学：纯文本即行为](#unix-config)
- [Agent 的「知识困境」](#knowledge-problem)
- [Skills：Agent 的配置文件](#skills-as-config)

### 第二部分：两层注入机制 ⚙️
- [为什么不把所有知识塞进 System Prompt](#why-not-system-prompt)
- [两层注入：廉价索引 + 按需加载](#two-layer)
- [工作流：Agent 如何「学会」一项技能](#workflow)

### 第三部分：代码实现 💻
- [Skill 文件格式](#skill-format)
- [SkillLoader：解析与管理](#skill-loader)
- [load_skill 工具：触发加载](#load-skill-tool)
- [完整代码](#full-code)

### 附录
- [常见问题 FAQ](#faq)

---

## 引言

你有没有想过，为什么 Unix 老手能把一台新机器在几分钟内配置成「顺手」的工作环境？

答案是 **dotfiles**：`.bashrc`、`.vimrc`、`.gitconfig`……一堆纯文本文件，存储着这个人积累多年的「操作技巧」。换台机器，把这些文件复制过去，行为立刻恢复。

**这个思路，可以启发 AI Agent 的知识管理设计。**

> **说明**：Claude Code 产品本身的 Skills（`/commit`、`/review-pr` 等）是通过 `Skill` 工具调用的**注册命令**，执行时展开为完整 prompt，并非用户可随意编辑的纯文本文件。本文介绍的是 `v4_agent.py` 中**受 Unix dotfiles 启发的自定义实现**——用 `.skills/*.md` 纯文本文件存储技能，是一种教学性的简化设计，展示「按需加载知识」这个核心思想。

本文将展示：如何用一个 `.md` 文件，让 Agent 在需要时「按需加载」专业知识——以及这个设计背后的 Unix 哲学根源。

---

<a id="part-1"></a>
## 第一部分：理论基础 🧠

<a id="unix-config"></a>
### Unix 配置哲学：纯文本即行为

Unix 有一个贯穿始终的设计决策：**用纯文本文件配置程序行为**。

```
Unix 配置文件生态
├── ~/.bashrc          → shell 启动行为、别名、函数
├── ~/.vimrc           → vim 编辑器行为
├── ~/.gitconfig       → git 工作流规范
├── /etc/hosts         → DNS 解析规则
├── ~/.ssh/config      → SSH 连接配置
└── .eslintrc          → 代码风格规范
```

这些文件有几个共同特征：

1. **纯文本**：人类可读，版本可控
2. **声明式**：描述「应该怎样」，而不是「如何实现」
3. **按需加载**：程序启动时读取，或运行时动态加载
4. **可组合**：多个配置文件叠加，行为叠加

最关键的一点：**这些文件改变的不是程序的代码，而是程序的行为。**

`.vimrc` 里加一行 `set number`，vim 就会显示行号。不需要重新编译 vim，不需要修改源码——一行文本，改变行为。

<a id="knowledge-problem"></a>
### Agent 的「知识困境」

现在考虑一个 AI Agent。它需要完成各种任务：

- 提交代码 → 需要知道 git 工作流规范
- 写测试 → 需要知道项目的测试框架和约定
- 部署服务 → 需要知道 Docker 命令和环境配置
- Code Review → 需要知道团队的代码风格

**问题来了：这些知识放在哪里？**

最直觉的答案是：放进 System Prompt。

```python
SYSTEM = """你是一个编程助手。

Git 规范：
- 提交信息格式：type(scope): description
- 分支命名：feature/xxx, fix/xxx
- 必须通过 CI 才能合并
...（500 tokens）

测试规范：
- 使用 pytest
- 覆盖率必须 > 80%
- 测试文件命名：test_xxx.py
...（300 tokens）

部署规范：
- 使用 Docker Compose
- 环境变量从 .env 读取
...（400 tokens）

代码风格：
...（600 tokens）
"""
```

这个方案有一个致命问题：**每次调用 API，这 1800 tokens 都要付费，不管这次任务用不用得上。**

更糟的是，随着规范越来越多，System Prompt 越来越长，LLM 的注意力会被稀释——重要信息淹没在噪音里。

<a id="skills-as-config"></a>
### Skills：Agent 的配置文件

Unix 的解法是：**不要把所有配置都加载，按需加载。**

shell 不会在启动时把所有可能用到的工具都加载进内存。它只加载基础环境，当你需要某个工具时，再去找它。

Agent 也可以这样：

```
传统方案（全量加载）:
System Prompt = 基础指令 + git规范 + 测试规范 + 部署规范 + ...
每次调用: 2000+ tokens

Skill Loading 方案（按需加载）:
System Prompt = 基础指令 + 技能索引（每个技能 ~20 tokens）
需要 git 时: 加载 git.md → 临时注入完整规范
每次调用: 200 tokens（基础）+ 按需加载
```

**Skills 就是 Agent 的配置文件。** 存储在 `.skills/` 目录下的纯文本 `.md` 文件，每个文件封装一项专业知识。

```
.skills/
├── git.md          → git 工作流规范
├── testing.md      → 测试最佳实践
├── deploy.md       → 部署操作手册
└── code-review.md  → Code Review 清单
```

---

<a id="part-2"></a>
## 第二部分：两层注入机制 ⚙️

<a id="why-not-system-prompt"></a>
### 为什么不把所有知识塞进 System Prompt

在深入实现之前，先理解为什么「全量加载」是个坏主意。

**问题 1：Token 成本**

```
每次 API 调用的 token 消耗：

全量加载:
  System Prompt: 3000 tokens（含所有规范）
  对话历史: 1000 tokens
  总计: 4000 tokens × N 次调用

按需加载:
  System Prompt: 300 tokens（仅索引）
  对话历史: 1000 tokens
  技能内容（按需）: 500 tokens（仅当前任务需要的）
  总计: 1800 tokens × N 次调用

节省: ~55%
```

**问题 2：注意力稀释**

LLM 的注意力是有限的。System Prompt 越长，每条指令获得的「注意力权重」越低。把不相关的规范塞进去，反而会干扰当前任务。

**问题 3：维护困难**

所有规范混在一个字符串里，难以独立更新、版本控制、复用。

<a id="two-layer"></a>
### 两层注入：廉价索引 + 按需加载

解决方案是**两层注入**：

```
第一层（廉价，始终存在）
┌─────────────────────────────────────┐
│ System Prompt:                      │
│                                     │
│ Skills available:                   │
│   - git: Git 工作流规范 [git, vcs]  │  ← 每个技能 ~20 tokens
│   - testing: 测试最佳实践 [pytest]  │
│   - deploy: 部署操作手册 [docker]   │
└─────────────────────────────────────┘

第二层（按需，仅在需要时加载）
┌─────────────────────────────────────┐
│ tool_result (load_skill "git"):     │
│                                     │
│ <skill name="git">                  │
│   # Git 工作流规范                  │  ← 完整内容，~500 tokens
│   ## 提交规范                       │
│   - type(scope): description        │
│   ## 分支规范                       │
│   ...                               │
│ </skill>                            │
└─────────────────────────────────────┘
```

第一层告诉 Agent「有哪些技能可用」，第二层在 Agent 需要时提供完整内容。

这和 Unix 的 `man` 命令异曲同工：你不需要把所有 man page 都背下来，需要时 `man git` 就能获取完整文档。

<a id="workflow"></a>
### 工作流：Agent 如何「学会」一项技能

```
用户: "帮我提交这次修改，写好 commit message"
         │
         ▼
┌─────────────────────┐
│ Agent 分析任务      │
│ → 这是 git 操作     │
│ → 需要 git 规范     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ load_skill("git")   │  ← 主动调用工具加载技能
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ tool_result:        │
│ <skill name="git">  │
│   完整 git 规范...  │  ← 技能内容注入上下文
│ </skill>            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Agent 现在「懂」git │
│ → 按规范执行操作    │
│ → git add, commit   │
└─────────────────────┘
```

关键洞察：**技能内容通过 `tool_result` 注入上下文，而不是预先写死在 System Prompt 里。** 这意味着技能是动态的、按需的、可组合的。

---

<a id="part-3"></a>
## 第三部分：代码实现 💻

<a id="skill-format"></a>
### Skill 文件格式

Skill 文件是带 YAML frontmatter 的 Markdown 文件，存放在 `.skills/` 目录：

```markdown
---
description: Git 工作流规范
tags: git, version-control, commit
---

# Git 工作流规范

## 提交信息格式

使用 Conventional Commits 规范：

```
type(scope): description

type 可选值:
- feat: 新功能
- fix: 修复 bug
- docs: 文档更新
- refactor: 重构
- test: 测试相关
```

## 分支规范

- 功能分支: feature/xxx
- 修复分支: fix/xxx
- 发布分支: release/vX.Y.Z

## 提交前检查

1. 运行测试: `pytest`
2. 检查 lint: `ruff check .`
3. 确认改动范围合理
```

**frontmatter 的作用**：
- `description`：第一层注入时显示的简短描述（~10 tokens）
- `tags`：帮助 Agent 判断何时需要加载这个技能

<a id="skill-loader"></a>
### SkillLoader：解析与管理

```python
class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills = {}
        self._load_all()

    def _load_all(self):
        """启动时扫描 .skills/ 目录，加载所有技能的元数据"""
        if not self.skills_dir.exists():
            return
        for f in sorted(self.skills_dir.glob("*.md")):
            name = f.stem
            text = f.read_text()
            meta, body = self._parse_frontmatter(text)
            self.skills[name] = {"meta": meta, "body": body}

    def _parse_frontmatter(self, text: str) -> tuple:
        """解析 YAML frontmatter，分离元数据和正文"""
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text
        meta = {}
        for line in match.group(1).strip().splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip()
        return meta, match.group(2).strip()

    def get_descriptions(self) -> str:
        """第一层：生成注入 System Prompt 的简短索引"""
        lines = []
        for name, skill in self.skills.items():
            desc = skill["meta"].get("description", "No description")
            tags = skill["meta"].get("tags", "")
            line = f"  - {name}: {desc}"
            if tags:
                line += f" [{tags}]"
            lines.append(line)
        return "\n".join(lines)

    def get_content(self, name: str) -> str:
        """第二层：返回完整技能内容，注入 tool_result"""
        skill = self.skills.get(name)
        if not skill:
            return f"Error: Unknown skill '{name}'"
        return f'<skill name="{name}">\n{skill["body"]}\n</skill>'
```

注意两个方法的分工：

- `get_descriptions()`：生成第一层，只有名称和描述，极度精简
- `get_content(name)`：生成第二层，完整内容，用 `<skill>` 标签包裹

<a id="load-skill-tool"></a>
### load_skill 工具：触发加载

```python
# 工具定义
{
    "name": "load_skill",
    "description": "Load specialized knowledge by name. Call this before tackling unfamiliar topics.",
    "input_schema": {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
}

# 工具执行
def execute_tool(name: str, args: dict) -> str:
    ...
    if name == "load_skill":
        return SKILL_LOADER.get_content(args["name"])
    ...
```

当 Agent 调用 `load_skill("git")` 时，`get_content("git")` 的返回值会作为 `tool_result` 追加到对话历史——这就是第二层注入的触发时机。

<a id="full-code"></a>
### 完整的两层注入流程

把所有部分串起来，看完整的数据流：

```python
# 1. 启动时：扫描技能目录
SKILL_LOADER = SkillLoader(WORKDIR / ".skills")

# 2. 构建 System Prompt：注入第一层（技能索引）
SYSTEM = f"""You are a coding agent at {WORKDIR}.

Use load_skill to access specialized knowledge before tackling unfamiliar topics.

Skills available:
{SKILL_LOADER.get_descriptions()}
# 输出示例:
#   - git: Git 工作流规范 [git, version-control]
#   - testing: 测试最佳实践 [pytest, coverage]
"""

# 3. Agent 运行时：调用 load_skill 触发第二层
# Agent 决策: "我需要 git 规范" → 调用 load_skill("git")
# tool_result: "<skill name="git">\n# Git 工作流规范\n...</skill>"
# 这段内容追加到 messages，Agent 现在「看到」了完整规范

# 4. Agent 基于完整规范执行任务
```

整个机制的精妙之处：**Agent 自己决定何时加载技能**。System Prompt 里的索引给了它「菜单」，它根据任务需要「点菜」。

---

<a id="faq"></a>
## 常见问题 FAQ

**Q: Agent 怎么知道什么时候该调用 load_skill？**

A: System Prompt 里有明确指令：`Use load_skill to access specialized knowledge before tackling unfamiliar topics.` 加上技能索引里的 tags，Agent 能判断当前任务是否需要某个技能。这和人类看到「不熟悉的领域先查文档」的直觉一致。

**Q: 技能内容会一直留在上下文里吗？**

A: 是的，一旦加载，技能内容就在当前对话的上下文里。这是合理的——同一个任务里，加载一次技能，后续步骤都能用到。跨对话不会保留（除非重新加载）。

**Q: 技能文件可以引用其他技能吗？**

A: 当前实现不支持技能间依赖。但 Agent 可以连续调用多个 `load_skill`，效果等同于组合多个技能。

**Q: 和 RAG（检索增强生成）有什么区别？**

A: RAG 是自动检索，Agent 不知道检索了什么。Skill Loading 是显式调用，Agent 主动决定加载哪个技能，更可控、更透明。适合「规范类」知识（有明确边界的专业知识），而不是「文档检索」场景。

---

## 📝 结语

从 Unix dotfiles 到 Agent Skills，这条线索清晰而优雅：

```
Unix 哲学: 纯文本配置程序行为
    ↓
.bashrc / .vimrc: 改变 shell/vim 的行为，无需修改代码
    ↓
.skills/*.md: 改变 Agent 的行为，无需修改 System Prompt
    ↓
两层注入: 廉价索引（始终存在）+ 按需加载（动态注入）
    ↓
Agent 按需「学会」任何技能
```

这不只是一个优化技巧。它揭示了一个更深的设计原则：

**知识和行为应该分离。** Agent 的核心逻辑（工具调用、循环、记忆）是稳定的；专业知识（git 规范、测试约定、部署流程）是可变的。把可变的部分外置为配置文件，就像 Unix 把行为配置外置为 dotfiles——系统保持简洁，知识保持灵活。


**系列导航**：
- **上一篇**:[04 - Multi-Agent：复杂任务的分解之道](https://juejin.cn/editor/drafts/7608937611306090548)
- **当前**:  [05 - 用纯文本文件教会 Agent 任何技能]()
- **下一篇**: 06 - 多层次上下文压缩