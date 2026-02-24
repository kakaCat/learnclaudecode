# 后端架构约束

⚠️ **开发前必读**

## 模块结构

```
backend/app/
├── config.py     # 模型配置
├── tools.py      # Tool 定义（@tool 装饰器）
└── agent.py      # Agent 循环（AgentService）
```

## 架构规范

### AgentService（agent.py）
- `AgentService.__init__`: 初始化 LLM + 绑定 tools
- `AgentService.run(prompt, history)`: 执行 agent 循环，返回最终文本

### Tools（tools.py）
- 每个 tool 用 `@tool` 装饰器定义
- 只负责执行，不包含业务逻辑

### Config（config.py）
- 所有环境变量读取集中在此
- 不在其他模块中直接读取 `os.getenv`

## ✅ 正确示例

```python
# agent.py - Service 只负责编排
class AgentService:
    def __init__(self):
        self.llm = build_llm().bind_tools(TOOLS)

    def run(self, prompt, history=None):
        # 循环调用 LLM + 执行 tools
        ...
```

## ❌ 禁止

- 在 tools.py 中直接调用 LLM
- 在 config.py 中包含业务逻辑
- 在 agent.py 中硬编码模型参数
