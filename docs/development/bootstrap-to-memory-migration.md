# .bootstrap → .memory 目录迁移完成

## 问题
代码中仍有两处引用旧的 `.bootstrap` 目录，但实际目录已改名为 `.memory`。

## 修改内容

### 1. backend/app/prompts.py:94
```python
# Before
core_instructions_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    ".bootstrap",
    "CORE_INSTRUCTIONS.md"
)

# After
core_instructions_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    ".memory",
    "CORE_INSTRUCTIONS.md"
)
```

### 2. backend/app/session/session.py:100
```python
# Before
# 初始化 Bootstrap 加载器（使用全局 .bootstrap 目录）
self._bootstrap_loader = GlobalMemoryLoader()

# After
# 初始化全局记忆加载器（使用全局 .memory 目录）
self._bootstrap_loader = GlobalMemoryLoader()
```

### 3. 文件迁移
```bash
# 移动文件
mv .bootstrap/CORE_INSTRUCTIONS.md .memory/

# 删除空目录
rmdir .bootstrap
```

## 验证结果

### 1. 语法检查
```bash
python -m py_compile backend/app/prompts.py backend/app/session/session.py
```
✅ 通过

### 2. 功能测试
```python
from backend.app.prompts import build_system_prompt

prompt = build_system_prompt('test', mode='full')
assert '工具失败处理规则' in prompt
```
✅ 核心指令加载成功
✅ 提示词长度: 10928 字符

### 3. 文件路径验证
```
核心指令路径: /Users/mac/Documents/ai/learnclaudecode/learnclaudecode/.memory/CORE_INSTRUCTIONS.md
文件存在: True
```
✅ 通过

### 4. 残留检查
```bash
grep -r "\.bootstrap" backend/
```
✅ 无残留引用（仅有已清理的缓存文件）

## 目录结构

### Before
```
learnclaudecode/
├── .bootstrap/
│   └── CORE_INSTRUCTIONS.md
└── .memory/
    ├── MEMORY.md
    └── ...
```

### After
```
learnclaudecode/
└── .memory/
    ├── CORE_INSTRUCTIONS.md  ⬅️ 新位置
    ├── MEMORY.md
    └── ...
```

## 相关常量

`backend/app/session/constants.py:16`
```python
# 全局记忆配置目录
MEMORY_DIR = PROJECT_ROOT / ".memory"
```
✅ 已正确配置

## 总结

- ✅ 所有 `.bootstrap` 引用已更新为 `.memory`
- ✅ `CORE_INSTRUCTIONS.md` 已移动到正确位置
- ✅ 空的 `.bootstrap` 目录已删除
- ✅ Python缓存已清理
- ✅ 功能测试通过

迁移完成！
