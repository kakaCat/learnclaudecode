# learnclaudecode

> 学习 Claude Code / AI Agent 开发的示例项目

## 项目信息
- 类型: CLI Agent 示例
- 技术栈: Python, Anthropic SDK, LangChain, DeepSeek
- 状态: 学习示例

## 目录结构

| 目录 | 说明 |
|------|------|
| `backend/` | Agent 核心代码 |
| `scripts/` | 启动脚本 |
| `docs/` | 文档 |

## 快速开始

```bash
# 安装依赖
pip install -r backend/requirements.txt

# 运行 Anthropic 版本
python v0_bash_agent.py

# 运行 LangChain + DeepSeek 版本
python scripts/run_langchain_deepseek.py
```

## 环境变量

```bash
ANTHROPIC_API_KEY=...          # Anthropic 版本
DEEPSEEK_API_KEY=...           # DeepSeek 版本
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1  # 可选
DEEPSEEK_MODEL=deepseek-chat   # 可选
```

## 架构守卫
- [后端架构约束](backend/ARCHITECTURE.md)
