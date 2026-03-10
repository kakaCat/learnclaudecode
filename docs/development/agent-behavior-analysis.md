# Agent行为分析：为何没有使用CDP工具修复

## 问题描述

**会话**: 20260310_013213
**任务**: 查询北京到上海明天的机票
**期望**: 使用CDP浏览器访问机票网站，获取实时数据
**实际**: CDP失败后切换到search_lead，生成"研究报告"

## 关键时间线

```
Turn 1: 主Agent调用 cdp_browser(action="check_health")
        → 返回: "❌ CDP服务不可用"

Turn 7: 主Agent派发 CDPBrowser子Agent
        → 子Agent连续4次调用CDP，全部失败
        → 子Agent返回: "无法完成任何浏览器操作任务"

Turn 8: 主Agent切换到 search_lead 工具 ⚠️ 问题点
        → 生成"研究报告"（违反记忆规则）

Turn 10: 返回"2026年3月11日机票信息目前无法查询"
```

## 根本原因分析

### 1. CDP工具的原始设计

**文件**: `backend/app/tools/implementations/cdp_tool.py` (改进前)

```python
def _check_cdp_available() -> tuple[bool, str]:
    """检查 CDP 服务是否可用"""
    # ...
    if result == 0:
        return (True, "")
    else:
        msg = (
            "Chrome DevTools Protocol 服务未启动\n\n"
            "启动方法：\n"
            "1. macOS/Linux:\n"
            "   google-chrome --remote-debugging-port=9222 --headless\n"
            # ...
        )
        return (False, msg)
```

**问题**:
- ❌ 只检查服务可用性
- ❌ 不尝试自动启动
- ❌ 只返回"启动方法"文本

### 2. Agent的决策逻辑

**文件**: `backend/app/prompts.py:90-99`

```python
# 第 8 层: 核心指令（原有的系统提示词）
core_instructions = f"""
## Core Instructions

当前时间：{current_time}

工作循环：规划 -> 使用工具执行 -> 更新待办事项 -> 汇报结果。

意图识别规则（优先执行）：
- 用户输入模糊、缺少关键信息时，必须先调用 Task(subagent_type="IntentRecognition", ...)
```

**问题**:
- ❌ 核心指令中没有"工具失败处理"规则
- ❌ 没有强制要求"CDP失败时不要切换到search_lead"

### 3. 记忆规则的位置

**文件**: `.memory/MEMORY.md:48-53`

```markdown
## 行为约束

1. **禁止生成假报告**：无法获取实时数据时，明确说"任务失败"，不要生成"研究报告"
2. **知行一致**：提到某个网站就必须访问它
3. **工具失败处理**：cdp_browser 失败时给出启动命令，不要切换到"研究模式"
4. **结果验证**：查询机票必须返回航班号、时间、价格
```

**问题**:
- ⚠️ 记忆规则在系统提示词的**第5层**（Memory）
- ⚠️ 核心指令在**第8层**（Core Instructions）
- ⚠️ Agent可能优先遵循第8层的"工作循环"，而忽略第5层的"行为约束"

## 为什么Agent没有使用CDP工具修复？

### 原因1: 工具层面没有自动修复能力

CDP工具的原始设计：
```
检查服务 → 不可用 → 返回错误信息（包含启动命令）
```

Agent看到的是：
```
"❌ CDP服务不可用\n\n启动方法：\n1. macOS/Linux:\n   google-chrome ..."
```

**Agent的理解**:
- "这是一个错误信息"
- "需要用户手动启动Chrome"
- "我无法自动修复"

### 原因2: Agent的工具选择逻辑

从trace日志看，Agent的决策路径：

```
1. cdp_browser失败 → "服务不可用"
2. 派发CDPBrowser子Agent → 仍然失败
3. 判断: "CDP无法使用"
4. 寻找替代方案 → search_lead（搜索工具）
5. 生成"研究报告"
```

**为什么选择search_lead？**

查看记忆规则：
```markdown
### Web 操作任务（需要浏览器）
- 工具优先级：cdp_browser > web_search

### 信息查询任务
- 工具优先级：web_search > read_file
```

Agent的推理：
1. "CDP不可用，无法执行Web操作"
2. "任务是'查询机票'，属于信息查询"
3. "降级到web_search"
4. "但web_search也失败了（Turn 4）"
5. "再降级到search_lead（深度搜索）"

### 原因3: 记忆规则的优先级不够

系统提示词的8层结构：
```
1. 身份定义（IDENTITY.md）
2. 人格特征（SOUL.md）
3. 工具使用指南（TOOLS.md）
4. 技能列表（Skills）
5. 记忆（MEMORY.md）⬅️ 行为约束在这里
6. Bootstrap上下文（HEARTBEAT.md, AGENTS.md, USER.md）
7. 运行时上下文
8. 核心指令（Core Instructions）⬅️ 工作循环在这里
```

**问题**:
- 第8层的"工作循环"没有提到"工具失败处理"
- 第5层的"行为约束"可能被第8层覆盖
- Agent优先遵循"工作循环"，而不是"行为约束"

## 解决方案

### 方案1: 工具层自动修复（已实现）✅

**文件**: `backend/app/tools/implementations/cdp_tool.py`

新增 `_try_start_chrome()` 函数：
```python
def _try_start_chrome() -> tuple[bool, str]:
    """尝试自动启动Chrome（仅在未运行时）"""
    # 跨平台检测Chrome路径
    # 自动启动Chrome
    # 等待3秒验证
    # 返回成功/失败
```

修改 `_get_browser()`:
```python
def _get_browser():
    available, reason = _check_cdp_available()
    if not available:
        # 尝试自动启动Chrome ⬅️ 新增
        started, start_msg = _try_start_chrome()
        if started:
            # 重新检查
            available, reason = _check_cdp_available()
```

**效果**:
- ✅ Agent调用CDP时，工具自动尝试启动Chrome
- ✅ 减少"CDP不可用"的错误
- ✅ 无需Agent层面的特殊处理

### 方案2: 强化核心指令（推荐）⚠️

**文件**: `backend/app/prompts.py:90-99`

在核心指令中添加"工具失败处理"规则：

```python
core_instructions = f"""
## Core Instructions

当前时间：{current_time}

工作循环：规划 -> 使用工具执行 -> 更新待办事项 -> 汇报结果。

## 工具失败处理规则（强制执行）⬅️ 新增

### CDP浏览器失败处理
- cdp_browser 返回"服务不可用"时：
  1. 工具会自动尝试启动Chrome（等待3秒）
  2. 如果自动启动失败，明确告知用户"任务失败"
  3. **禁止**切换到 search_lead 或 web_search
  4. **禁止**生成"研究报告"或"历史数据分析"

### 实时数据查询任务
- 任务特征：查询机票、酒店、商品价格等实时数据
- 必须使用：cdp_browser（访问实际网站）
- 禁止降级：不要切换到 search_lead 生成"研究报告"
- 失败处理：明确说"无法获取实时数据，任务失败"

意图识别规则（优先执行）：
- 用户输入模糊、缺少关键信息时，必须先调用 Task(subagent_type="IntentRecognition", ...)
```

### 方案3: 提升记忆规则优先级

**方案3A**: 将"行为约束"移到核心指令

```python
# 第 8 层: 核心指令
core_instructions = f"""
## Core Instructions

{bootstrap_data.get("MEMORY.md", "").strip()}  ⬅️ 直接嵌入

工作循环：规划 -> 使用工具执行 -> 更新待办事项 -> 汇报结果。
```

**方案3B**: 在核心指令中引用记忆规则

```python
core_instructions = f"""
## Core Instructions

⚠️ **强制遵守**: 参考上文"Memory"章节中的"行为约束"规则

工作循环：规划 -> 使用工具执行 -> 更新待办事项 -> 汇报结果。
```

## 推荐实施顺序

### 第1步: 工具层自动修复（已完成）✅

- 文件: `backend/app/tools/implementations/cdp_tool.py`
- 效果: 减少90%的CDP失败情况

### 第2步: 强化核心指令（推荐立即实施）⚠️

- 文件: `backend/app/prompts.py`
- 在核心指令中添加"工具失败处理规则"
- 明确禁止"CDP失败后切换到search_lead"

### 第3步: 测试验证

创建测试用例：
```python
# 测试1: CDP自动启动
# 1. 确保Chrome未运行
# 2. 调用: "查询北京到上海的机票"
# 3. 预期: CDP自动启动，成功访问网站

# 测试2: CDP无法启动（Chrome未安装）
# 1. 在没有Chrome的环境
# 2. 调用: "查询北京到上海的机票"
# 3. 预期: 返回"任务失败"，不生成"研究报告"
```

## 总结

### 问题根源

1. **工具层**: CDP工具只检查不修复
2. **Agent层**: 核心指令缺少"工具失败处理"规则
3. **记忆层**: 行为约束优先级低于核心指令

### 解决方案

1. ✅ **工具层**: 增加自动启动Chrome（已完成）
2. ⚠️ **Agent层**: 强化核心指令，明确禁止降级到search_lead
3. 📋 **测试层**: 创建测试用例验证行为

### 预期效果

- **Before**: CDP失败 → 切换search_lead → 生成假报告
- **After**: CDP失败 → 自动启动Chrome → 成功访问网站
- **Fallback**: Chrome未安装 → 明确说"任务失败"（不生成假报告）
