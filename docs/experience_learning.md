# 经验学习系统 (Experience Learning System)

## 概述

这是一个**强化学习式的自我进化系统**，从 session 的执行轨迹（trace.jsonl）中提取成功的工具使用模式，写入记忆文件，让 Agent 越用越聪明。

## 两阶段设计

### 阶段1：强化学习 - 提取成功模式

从 trace.jsonl 中分析：
- ✅ 哪些工具调用序列成功了
- ✅ 哪些参数组合有效
- ✅ 哪些错误尝试可以避免
- ✅ 写入 `backend/memory/TOOLS.md` 和 `MEMORY.md`

### 阶段2：技能沉淀 - 生成可复用 Skill

当某个模式重复出现且稳定时：
- 🎯 自动生成 `.skills/{skill_name}.md`
- 🎯 封装为可调用的技能
- 🎯 下次直接用 skill 而不是多次试错

## 使用方法

### 1. 分析单个 session

```bash
# 分析指定 session
python scripts/learn_from_session.py .sessions/20260313_162148

# 分析最新 session
python scripts/learn_from_session.py --latest

# Dry-run 模式（只分析不写入）
python scripts/learn_from_session.py .sessions/20260313_162148 --dry-run
```

### 2. 批量学习所有 session

```bash
# 分析所有 session
python scripts/learn_from_session.py --all

# Dry-run 模式
python scripts/learn_from_session.py --all --dry-run
```

## 输出示例

```
📂 分析指定 session: 20260313_162148

============================================================
📊 分析 session: 20260313_162148
============================================================

任务: 查询北京到厦门的航班信息...
状态: ✅ 成功
工具调用: 6 次
发现模式: 1 个
Skill 候选: 1 个

💾 写入记忆文件...
✅ 已更新 TOOLS.md 和 MEMORY.md

🎯 生成 Skill...
✅ 生成了 0 个 skill

============================================================
📈 学习总结
============================================================
分析 session 数: 1
提取模式数: 1
生成 skill 数: 0
```

## 学习结果

### 写入 TOOLS.md

在 `backend/memory/TOOLS.md` 末尾添加：

```markdown
## 强化学习经验 (2026-03-14 01:16:36)

### Web Query 任务

**关键词**: 航班, 查询

**推荐工具序列**: spawn_subagent → curl → curl → curl → curl → workspace_list

**成功次数**: 1
```

### 写入 MEMORY.md

在 `backend/memory/MEMORY.md` 末尾添加：

```markdown
## 2026-03-14 01:16:36

**本次学习**: 分析了 1 个工具调用序列

**成功模式**:
- web_query: 1 次成功

**可生成技能**: 1 个候选
```

## 工作原理

### 1. 事件提取

从 trace.jsonl 中提取关键事件：
- `main_agent.start` - 任务开始
- `main.tool_start` - 工具调用开始
- `main.tool_end` - 工具调用结束
- `main_agent.end` / `main_agent.error` - 任务结束/失败

### 2. 模式识别

#### 任务分类
- `web_query` - 机票、航班、酒店、预订
- `content_generation` - 网页、HTML、展示
- `system_development` - 开发、实现、构建、系统
- `information_search` - 查询、搜索、什么是
- `general` - 其他

#### 成功判断
- 检查 `main_agent.end` 事件
- 检查最后的 LLM 输出是否包含成功标志（"已完成"、"成功"、"✅"）

### 3. Skill 生成策略

#### 策略1: 重复模式（至少2次）
```python
if len(patterns) >= 2:
    # 检查工具序列是否稳定
    # 如果相同序列出现 >= 2 次，生成 skill
```

#### 策略2: 复杂单次成功（工具调用 >= 3 次）
```python
if len(tool_sequence) >= 3 and "spawn_subagent" in tool_sequence:
    # 单次但复杂的成功模式，也可以生成 skill
```

## 核心代码

### ExperienceLearner 类

```python
class ExperienceLearner:
    """经验学习器 - 强化学习式的工具使用优化"""

    def analyze_session(self) -> Dict[str, Any]:
        """分析整个 session 的执行轨迹"""
        # 1. 提取任务描述
        # 2. 提取工具调用序列
        # 3. 判断任务是否成功
        # 4. 分析成功/失败模式
        # 5. 识别 skill 候选

    def write_to_memory(self):
        """将学习结果写入记忆文件"""
        # 1. 更新 TOOLS.md
        # 2. 更新 MEMORY.md

    def _generate_skills(self) -> List[str]:
        """生成 skill 文件"""
        # 为每个 skill 候选生成 .skills/{name}.md
```

## 未来改进

### 短期（已实现）
- ✅ 从 trace.jsonl 提取工具调用序列
- ✅ 识别成功/失败模式
- ✅ 写入记忆文件
- ✅ 批量学习多个 session

### 中期（待实现）
- ⏳ 自动生成 skill 文件
- ⏳ 参数模式提取（不仅是工具序列，还有参数组合）
- ⏳ 错误模式避免（记录失败的尝试）
- ⏳ 相似任务推荐（根据关键词匹配历史成功模式）

### 长期（规划中）
- 🔮 多 session 聚合分析（跨会话学习）
- 🔮 A/B 测试（对比不同工具序列的成功率）
- 🔮 自动优化工具选择（基于历史数据）
- 🔮 技能版本管理（skill 的迭代优化）

## 配置

### 记忆文件位置
- `backend/memory/TOOLS.md` - 工具使用经验
- `backend/memory/MEMORY.md` - 通用记忆
- `.skills/` - 生成的技能文件（未来）

### 阈值配置

在 `experience_learner.py` 中可调整：

```python
# Skill 生成阈值
MIN_REPEAT_COUNT = 2  # 重复模式至少出现次数
MIN_TOOL_COUNT = 3    # 复杂模式最少工具调用次数
```

## 最佳实践

### 1. 定期学习
```bash
# 每天结束时批量学习
python scripts/learn_from_session.py --all
```

### 2. 增量学习
```bash
# 每次重要任务完成后立即学习
python scripts/learn_from_session.py --latest
```

### 3. 验证学习结果
```bash
# 先 dry-run 查看会学到什么
python scripts/learn_from_session.py --all --dry-run

# 确认后再实际写入
python scripts/learn_from_session.py --all
```

## 示例场景

### 场景1: 机票查询任务

**输入**: "查询北京到厦门的航班信息"

**学习到的模式**:
```
任务类型: web_query
关键词: 航班, 查询
工具序列: spawn_subagent → curl → curl → curl → curl → workspace_list
成功次数: 1
```

**效果**: 下次遇到类似任务时，Agent 会优先使用这个工具序列

### 场景2: 重复模式识别

当同一类型任务成功 2 次以上时：
```
任务类型: web_query
工具序列: spawn_subagent → curl → workspace_list
成功次数: 3
```

**效果**: 自动生成 skill，下次直接调用

## 技术细节

### trace.jsonl 格式

```json
{"ts": 1773421168.969, "event": "main_agent.start", "prompt": "查询航班"}
{"ts": 1773421185.05, "event": "main.tool_start", "tool": "spawn_subagent", "inputs": {...}}
{"ts": 1773421955.043, "event": "main.tool_end", "tool": "spawn_subagent"}
{"ts": 1773422000.123, "event": "main_agent.end"}
```

### 关键事件
- `main_agent.start` - 提取任务描述
- `main.tool_start` - 提取工具名称和参数
- `main_agent.end` - 判断成功
- `main_agent.error` - 判断失败

## 总结

这个经验学习系统实现了：

1. ✅ **自动化学习**: 无需手动总结，自动从执行轨迹中学习
2. ✅ **持久化记忆**: 写入记忆文件，跨会话保留
3. ✅ **模式识别**: 识别成功的工具使用模式
4. ✅ **批量处理**: 支持分析所有历史 session
5. ⏳ **技能沉淀**: 将重复模式封装为可复用的 skill（待完善）

通过这个系统，Agent 会随着使用次数增加而变得越来越聪明，减少试错次数，提高任务成功率。
