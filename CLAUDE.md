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

## File Writing
- 写超过 200 行的文件时，必须分段写，每段 ≤150 行
- 每段写完后运行 `python -m py_compile <file>` 验证语法
- 禁止单次 Write 超过 12800 字符

## Agent Version Upgrades
- 升级时逐模块进行，一次只写一个文件
- 每个文件写完验证语法后再继续
- 不要一次性生成整个 agent 文件

## Blog Writing
- 写博客前必须 grep/read 所有涉及的源文件，列出关键事实清单
- 不得将本项目的自定义机制（如 .skills/*.md 加载）与 Claude Code 内置功能混淆
- 每个技术声明必须能引用到具体文件和行号
- 写完后逐条核对，不符合源码的内容必须修改
