# 共享资源机制说明

## 核心设计：组合模式 + 属性引用

### 1. MainContext 拥有所有共享资源

```python
class MainContext:
    def __init__(self, session_key: str):
        # 创建共享资源（只创建一次）
        self.session_store = get_store()  # 全局单例
        self.llm = get_llm()
        self.tracer = Tracer()
        self.conversation_history = ConversationHistory(...)
        self.overflow_guard = OverflowGuard(...)
```

### 2. SubagentContext 引用 MainContext

```python
class SubagentContext:
    def __init__(self, main_context: MainContext, subagent_type: str):
        # 保存对 MainContext 的引用
        self.main_context = main_context  # ← 关键：引用而非复制

        # 通过 @property 提供便捷访问
        @property
        def session_store(self):
            return self.main_context.session_store  # ← 返回同一个对象

        @property
        def llm(self):
            return self.main_context.llm  # ← 返回同一个对象
```

### 3. 数据流示例

```
创建阶段：
┌─────────────────────────────────────┐
│ main_context = MainContext("s001")  │
│   ├─ session_store: 0x12345         │  ← 创建实例
│   ├─ llm: 0x67890                   │  ← 创建实例
│   └─ tracer: 0xABCDE                 │  ← 创建实例
└─────────────────────────────────────┘
              │
              │ 传递引用
              ▼
┌─────────────────────────────────────┐
│ sub_context = SubagentContext(      │
│     main_context,  ← 引用           │
│     "Explore"                        │
│ )                                    │
│   └─ main_context: 0x12300          │  ← 指向 MainContext
└─────────────────────────────────────┘

访问阶段：
sub_context.session_store
    ↓ 通过 @property
    ↓ return self.main_context.session_store
    ↓
    返回 0x12345  ← 与 main_context.session_store 是同一个对象！
```

### 4. 验证共享（Python 对象 ID）

```python
# 测试代码
main_ctx = MainContext("test")
sub_ctx = main_ctx.create_subagent("Explore")

# 验证是同一个对象（内存地址相同）
assert id(main_ctx.session_store) == id(sub_ctx.session_store)  # ✅
assert id(main_ctx.llm) == id(sub_ctx.llm)                      # ✅
assert id(main_ctx.tracer) == id(sub_ctx.tracer)                # ✅

# 验证引用关系
assert sub_ctx.main_context is main_ctx  # ✅ 是同一个对象
```

### 5. 实际使用场景

```python
# Main Agent 保存数据
main_service = AgentService(main_context)
main_service.context.session_store.save_turn("main", user_msg, ai_msg)
    ↓
    写入 .sessions/20260310_120000/main.jsonl

# Subagent 保存数据
sub_context = main_context.create_subagent("Explore")
sub_service = AgentService(sub_context)
sub_service.context.session_store.save_turn("Explore", user_msg, ai_msg)
    ↓
    写入 .sessions/20260310_120000/Explore.jsonl  ← 同一个会话目录！
```

### 6. 关键优势

**内存效率**
- LLM 实例只创建一次（避免重复初始化）
- SessionStore 是全局单例（所有 Context 共享）

**数据一致性**
- 所有 Agent 写入同一个 session 目录
- session_key 保证一致

**清晰的依赖关系**
```
MainContext (拥有者)
    ↓ 引用
SubagentContext (使用者)
    ↓ 通过 @property 访问
AgentService (消费者)
```

### 7. 与旧架构对比

**旧架构（重复创建）**
```python
def run_subagent(...):
    llm = ChatOpenAI(...)  # ❌ 重新创建
    agent = create_agent(llm, ...)
    # 独立的执行逻辑
```

**新架构（共享资源）**
```python
sub_context = main_context.create_subagent("Explore")
# ✅ sub_context.llm 就是 main_context.llm
# ✅ sub_context.session_store 就是 main_context.session_store
```

### 8. Python 引用机制

```python
# Python 中的对象引用
a = [1, 2, 3]
b = a  # b 引用 a，不是复制

b.append(4)
print(a)  # [1, 2, 3, 4]  ← a 也变了！

# 同样的原理
sub_context.main_context = main_context  # 引用
sub_context.session_store  # 返回 main_context.session_store（同一个对象）
```

## 总结

共享机制的核心是：
1. **MainContext 创建资源**（拥有者）
2. **SubagentContext 保存引用**（`self.main_context = main_context`）
3. **通过 @property 访问**（`return self.main_context.xxx`）
4. **Python 引用语义保证是同一个对象**

这样就实现了：
- ✅ 资源共享（不重复创建）
- ✅ 数据一致（写入同一个 session）
- ✅ 依赖清晰（显式引用，不依赖全局状态）
