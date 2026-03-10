# 核心指令加载机制重构

## 问题
`backend/app/prompts.py` 中直接拼接路径加载 `CORE_INSTRUCTIONS.md`，违反了统一的 session 管理原则。

## 原始代码（不规范）
```python
# 第 8 层: 核心指令（从文件加载）
# 计算项目根目录: backend/app/prompts.py -> backend/app -> backend -> 项目根
core_instructions_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    ".memory",
    "CORE_INSTRUCTIONS.md"
)

core_instructions = ""
if os.path.exists(core_instructions_path):
    with open(core_instructions_path, "r", encoding="utf-8") as f:
        core_instructions = f.read().strip()
```

**问题**:
1. ❌ 直接拼接路径，绕过了 session 管理
2. ❌ 硬编码 `.memory` 目录名
3. ❌ 使用 `os.path.join` 和 `__file__` 计算路径
4. ❌ 直接 `open()` 读取文件，没有缓存

## 重构后代码（规范）
```python
# 第 8 层: 核心指令（从全局记忆加载）
# 使用 GlobalMemoryLoader 统一管理，避免直接拼接路径
# CORE_INSTRUCTIONS.md 应该通过 session 的 bootstrap_data 加载
core_instructions = ""
if session_key and mode != "none":
    # 优先从 bootstrap_data 获取（已通过 load_bootstrap 加载）
    core_instructions = bootstrap_data.get("CORE_INSTRUCTIONS.md", "").strip()

if not core_instructions:
    # 降级：直接从 GlobalMemoryLoader 加载（无 session 或未加载时）
    from backend.app.session.memory import GlobalMemoryLoader
    loader = GlobalMemoryLoader()
    core_instructions = loader.load_file("CORE_INSTRUCTIONS.md").strip()
```

**优点**:
1. ✅ 通过 `GlobalMemoryLoader` 统一管理
2. ✅ 路径由 `MEMORY_DIR` 常量定义（`backend/app/session/constants.py`）
3. ✅ 支持缓存（`GlobalMemoryLoader._cache`）
4. ✅ 优先从 `bootstrap_data` 获取（已加载）
5. ✅ 降级机制：无 session 时直接加载

## 配套修改

### 1. 添加到全局记忆文件列表

**文件**: `backend/app/session/memory.py:18-27`

```python
# 全局记忆文件列表
GLOBAL_MEMORY_FILES = [
    "SOUL.md",
    "IDENTITY.md",
    "TOOLS.md",
    "USER.md",
    "HEARTBEAT.md",
    "BOOTSTRAP.md",
    "AGENTS.md",
    "MEMORY.md",
    "CORE_INSTRUCTIONS.md",  # 核心指令（系统提示词第8层）⬅️ 新增
]
```

**作用**: 确保 `load_bootstrap()` 会自动加载 `CORE_INSTRUCTIONS.md`

## 加载流程

### 有 session 时（推荐）
```
1. build_system_prompt(session_key="test", mode="full")
2. store.load_bootstrap(mode="full")
3. GlobalMemoryLoader.load_all(mode="full")
4. 遍历 GLOBAL_MEMORY_FILES，加载所有文件（包括 CORE_INSTRUCTIONS.md）
5. 返回 bootstrap_data = {"CORE_INSTRUCTIONS.md": "...", ...}
6. prompts.py 从 bootstrap_data 获取
```

### 无 session 时（降级）
```
1. build_system_prompt(session_key="", mode="full")
2. bootstrap_data = {}（空）
3. core_instructions = bootstrap_data.get("CORE_INSTRUCTIONS.md", "")（空）
4. 降级：直接创建 GlobalMemoryLoader 加载
5. loader.load_file("CORE_INSTRUCTIONS.md")
```

## 路径管理

所有全局记忆文件的路径由 `MEMORY_DIR` 常量统一管理：

**文件**: `backend/app/session/constants.py:16`
```python
# 全局记忆配置目录
MEMORY_DIR = PROJECT_ROOT / ".memory"
```

**优点**:
- ✅ 单一真相来源（Single Source of Truth）
- ✅ 修改目录名只需改一处
- ✅ 所有代码通过 `MEMORY_DIR` 引用

## 验证结果

### 语法检查
```bash
python -m py_compile backend/app/prompts.py backend/app/session/memory.py
```
✅ 通过

### 功能测试
```python
from backend.app.prompts import build_system_prompt

prompt = build_system_prompt('test', mode='full')
assert '工具失败处理规则' in prompt
```
✅ 核心指令加载成功
✅ 提示词长度: 10928 字符

## 最佳实践

### ✅ 推荐做法
```python
# 1. 通过 session 加载（有缓存）
store = get_store()
store.set_current_key(session_key)
bootstrap_data = store.load_bootstrap(mode="full")
content = bootstrap_data.get("CORE_INSTRUCTIONS.md", "")

# 2. 直接使用 GlobalMemoryLoader（无 session）
from backend.app.session.memory import GlobalMemoryLoader
loader = GlobalMemoryLoader()
content = loader.load_file("CORE_INSTRUCTIONS.md")
```

### ❌ 不推荐做法
```python
# 1. 直接拼接路径
path = os.path.join(PROJECT_ROOT, ".memory", "CORE_INSTRUCTIONS.md")
with open(path) as f:
    content = f.read()

# 2. 硬编码目录名
path = "/Users/xxx/project/.memory/CORE_INSTRUCTIONS.md"
with open(path) as f:
    content = f.read()

# 3. 使用 __file__ 计算路径
path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    ".memory",
    "CORE_INSTRUCTIONS.md"
)
```

## 总结

### 修改内容
1. ✅ `backend/app/prompts.py:90-102` - 使用 `GlobalMemoryLoader` 加载
2. ✅ `backend/app/session/memory.py:18-27` - 添加 `CORE_INSTRUCTIONS.md` 到列表

### 优点
- ✅ 统一的路径管理（`MEMORY_DIR`）
- ✅ 统一的加载机制（`GlobalMemoryLoader`）
- ✅ 支持缓存
- ✅ 降级机制

### 原则
**所有全局记忆文件的加载都应该通过 `GlobalMemoryLoader`，而不是直接拼接路径和 `open()` 读取。**

---

**修改日期**: 2026-03-10
**修改原因**: 统一 session 管理，避免直接拼接路径
**影响范围**: 核心指令加载机制
