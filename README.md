# Learn Claude Code - AI Agent 开发学习项目

> 学习 Claude Code / AI Agent 开发的完整示例项目，包含多个版本的实现和倒排索引算法示例。

## 📋 项目概述

这是一个用于学习和实践 AI Agent 开发的项目，展示了如何构建类似 Claude Code 的代码助手 Agent。项目包含从基础到高级的多个版本实现，以及一个完整的倒排索引算法示例。

## 🏗️ 项目结构

```
.
├── backend/                    # Agent 后端核心代码
│   ├── app/
│   │   ├── agent.py           # Agent 服务主逻辑
│   │   ├── config.py          # 模型配置
│   │   └── tools.py           # Tool 定义
│   ├── ARCHITECTURE.md        # 架构约束文档
│   └── requirements.txt       # Python 依赖
├── scripts/                   # 启动脚本
│   └── run_langchain_deepseek.py
├── blog/                      # 学习笔记
│   └── v2.md
├── v0_bash_agent.py           # v0: 基础 Bash Agent
├── v0_langchain_deepseek_agent.py # v0: LangChain + DeepSeek
├── v1_basic_agent.py          # v1: 基础 Agent (4个核心工具)
├── v2_agent.py                # v2: 增强 Agent (7个工具)
├── v2_todo_agent.py           # v2: 带任务列表的 Agent
├── v3_agent.py                # v3: 完整 Agent 实现
├── README_inverted_index.md   # 倒排索引算法文档
└── CLAUDE.md                  # 项目简要说明
```

## 🚀 快速开始

### 环境准备

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd learnclaudecode
   ```

2. **安装依赖**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **配置环境变量**
   复制 `.env.example` 为 `.env` 并填入你的 API 密钥：
   ```bash
   cp .env.example .env
   ```
   编辑 `.env` 文件：
   ```env
   # Anthropic Claude API (用于 v0-v3)
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   
   # DeepSeek API (用于 LangChain 版本)
   DEEPSEEK_API_KEY=your_deepseek_api_key_here
   DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
   DEEPSEEK_MODEL=deepseek-chat
   ```

### 运行不同版本的 Agent

#### 版本 0: 基础实现
```bash
# 基础 Bash Agent (Anthropic)
python v0_bash_agent.py

# LangChain + DeepSeek 版本
python scripts/run_langchain_deepseek.py
```

#### 版本 1: 基础 Agent (4个核心工具)
```bash
python v1_basic_agent.py
```
**特点**: 包含 4 个核心工具：`bash`, `read_file`, `write_file`, `edit_file`

#### 版本 2: 增强 Agent (7个工具)
```bash
python v2_agent.py
```
**特点**: 新增 3 个只读探索工具：`glob`, `grep`, `list_dir`

#### 版本 2.5: 带任务列表的 Agent
```bash
python v2_todo_agent.py
```
**特点**: 添加任务跟踪功能，支持多步骤任务管理

#### 版本 3: 完整实现
```bash
python v3_agent.py
```
**特点**: 完整的 Agent 实现，包含所有功能

## 🛠️ 核心概念

### Agent 架构模式
```
用户输入 → Agent → 工具调用 → 结果 → 决策 → ... → 最终响应
```

### 核心工具集

| 工具 | 用途 | 替代的 bash 命令 |
|------|------|-----------------|
| `bash` | 执行 shell 命令 | 所有命令 |
| `read_file` | 读取文件内容 | `cat`, `head`, `tail` |
| `write_file` | 创建/覆盖文件 | `echo >`, `cat >` |
| `edit_file` | 修改文件内容 | `sed`, `vim` |
| `glob` | 文件模式匹配 | `find . -name "*.py"` |
| `grep` | 文本搜索 | `grep -rn "pattern"` |
| `list_dir` | 目录列表 | `ls -la` |

### 后端架构

项目遵循清晰的架构约束：
- **agent.py**: Agent 服务主逻辑，负责编排 LLM 调用和工具执行
- **tools.py**: 工具定义，使用 `@tool` 装饰器
- **config.py**: 环境变量和模型配置集中管理

详细架构规范见 [backend/ARCHITECTURE.md](backend/ARCHITECTURE.md)。

## 📚 学习路径

### 阶段 1: 理解基础概念
1. 阅读 `v1_basic_agent.py` - 理解 "Model as Agent" 核心思想
2. 运行基础版本，观察 Agent 如何工作

### 阶段 2: 探索增强功能
1. 阅读 `v2_agent.py` - 学习只读探索工具的重要性
2. 对比 v1 和 v2 的差异，理解工具设计原则

### 阶段 3: 学习任务管理
1. 阅读 `v2_todo_agent.py` - 学习多步骤任务跟踪
2. 理解任务状态管理的重要性

### 阶段 4: 实践完整实现
1. 阅读 `v3_agent.py` - 查看完整实现
2. 运行完整版本，体验完整功能

### 阶段 5: 后端架构
1. 阅读 `backend/app/` 中的代码
2. 理解模块化设计和架构约束

## 🔍 倒排索引算法

项目还包含一个完整的倒排索引算法实现，用于学习和演示搜索引擎核心技术：

### 主要功能
- **文档索引**: 添加文档到倒排索引
- **文本预处理**: 小写转换、去除标点、停用词过滤
- **TF-IDF搜索**: 基于词频-逆文档频率的相关性排序
- **布尔搜索**: 支持 AND 操作的精确匹配
- **短语搜索**: 精确短语匹配

### 运行示例
```bash
# 查看详细文档
cat README_inverted_index.md

# 运行演示
python inverted_index.py
```

详细文档见 [README_inverted_index.md](README_inverted_index.md)。

## 🎯 学习目标

通过本项目，你将学习到：

1. **AI Agent 核心原理**: 理解 "Model as Agent" 的设计思想
2. **工具调用机制**: 学习如何设计和实现 Agent 工具
3. **任务管理**: 掌握多步骤任务的跟踪和管理
4. **架构设计**: 学习模块化、可维护的 Agent 架构
5. **安全考虑**: 理解路径沙箱、命令过滤等安全机制
6. **搜索引擎算法**: 掌握倒排索引和 TF-IDF 算法

## ⚠️ 注意事项

1. **API 密钥安全**: 不要将 `.env` 文件提交到版本控制
2. **路径安全**: 所有工具都包含路径沙箱检查，防止目录逃逸
3. **命令过滤**: `bash` 工具包含危险命令过滤
4. **资源限制**: 工具执行有超时和输出长度限制

## 📖 学习资源

- [Claude Code 官方文档](https://docs.anthropic.com/claude/code)
- [LangChain 文档](https://python.langchain.com/docs/)
- [倒排索引算法原理](https://en.wikipedia.org/wiki/Inverted_index)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进本项目！

## 📄 许可证

MIT License