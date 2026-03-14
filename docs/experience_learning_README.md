# 经验学习系统 - 完整实现

## 🎯 功能概述

一个**强化学习式的自我进化系统**，从 session 执行轨迹中提取成功模式，让 Agent 越用越聪明。

## 📦 核心组件

### 1. 纯规则版本
- **文件**: `backend/app/tools/implementations/experience_learner.py`
- **特点**: 快速、免费、基础筛选
- **适用**: 快速原型、成本敏感场景

### 2. LLM 增强版本
- **文件**: `backend/app/tools/implementations/experience_learner_llm.py`
- **特点**: 智能去重、质量评估、语义理解
- **适用**: 生产环境、长期使用

### 3. 命令行工具
- **纯规则**: `scripts/learn_from_session.py`
- **LLM 增强**: `scripts/learn_from_session_llm.py`

## 🚀 快速开始

### 安装依赖
```bash
pip install -r backend/requirements.txt
```

### 基础使用（纯规则）
```bash
# 分析最新 session
python scripts/learn_from_session.py --latest

# 分析所有 session
python scripts/learn_from_session.py --all

# Dry-run 模式
python scripts/learn_from_session.py --latest --dry-run
```

### 高级使用（LLM 增强）
```bash
# 分析最新 session（推荐）
python scripts/learn_from_session_llm.py --latest

# 分析所有 session
python scripts/learn_from_session_llm.py --all

# 禁用 LLM（降级到规则系统）
python scripts/learn_from_session_llm.py --latest --no-llm
```

## 📊 效果对比

| 特性 | 纯规则系统 | LLM 增强系统 |
|------|-----------|-------------|
| 去重能力 | ❌ 精确匹配 | ✅ 语义理解 |
| 质量评估 | ❌ 无 | ✅ 有 |
| 处理速度 | ✅ 快 (~1s) | ⚪ 中等 (~3-5s) |
| API 成本 | ✅ 免费 | ⚪ 低 (~0.001元/session) |
| 记忆质量 | ❌ 低（重复、泛化） | ✅ 高（去重、精准） |

## 💡 工作原理

### 两阶段设计

#### 阶段1: 强化学习 - 提取成功模式
```
trace.jsonl → 提取工具序列 → 识别成功模式 → 写入记忆
```

#### 阶段2: 技能沉淀 - 生成可复用 Skill
```
重复模式 → 识别候选 → 生成 skill → 下次直接调用
```

### LLM 增强的关键环节

1. **质量评估**
   ```python
   # LLM 判断模式是否值得记录
   evaluation = llm.evaluate(pattern)
   if evaluation['should_record']:
       record_to_memory(pattern)
   ```

2. **智能去重**
   ```python
   # LLM 识别语义上的重复
   action = llm.check_duplicate(new_pattern, existing)
   if action == "skip":
       print("跳过重复模式")
   ```

3. **生成总结**（待完善）
   ```python
   # LLM 生成有意义的总结
   summary = llm.summarize(patterns)
   ```

## 📖 文档

- [使用指南](docs/experience_learning.md) - 详细使用说明
- [为什么需要 LLM](docs/why_llm_for_learning.md) - 设计理念
- [测试报告](docs/llm_learning_test_report.md) - 效果对比

## 🎯 实际效果

### 问题：纯规则系统的重复记录

查看 `backend/memory/TOOLS.md`：
```markdown
## 强化学习经验 (2026-03-14 01:16:01)
### Web Query 任务
**推荐工具序列**: spawn_subagent → curl → curl → curl → curl → workspace_list

## 强化学习经验 (2026-03-14 01:16:16)
### Web Query 任务
**推荐工具序列**: spawn_subagent → curl → curl → curl → curl → workspace_list

## 强化学习经验 (2026-03-14 01:16:36)
### Web Query 任务
**推荐工具序列**: spawn_subagent → curl → curl → curl → curl → workspace_list
```

❌ 相同模式重复记录 3 次

### 解决：LLM 智能去重

```bash
python scripts/learn_from_session_llm.py .sessions/20260313_162148
```

输出：
```
  跳过重复模式: web_query
  没有发现值得记录的新模式
```

✅ LLM 识别重复并自动跳过

## 🔧 配置

### 环境变量
```bash
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

### 阈值配置

在 `experience_learner.py` 中：
```python
MIN_REPEAT_COUNT = 2  # 重复模式至少出现次数
MIN_TOOL_COUNT = 3    # 复杂模式最少工具调用次数
```

## 📈 使用建议

### 日常工作流

```bash
# 每次重要任务完成后
python scripts/learn_from_session_llm.py --latest

# 每周批量学习一次
python scripts/learn_from_session_llm.py --all
```

### 成本优化

```bash
# 先 dry-run 查看
python scripts/learn_from_session_llm.py --all --dry-run

# 确认后再写入
python scripts/learn_from_session_llm.py --all
```

### 降级策略

```bash
# 网络不稳定时使用纯规则
python scripts/learn_from_session.py --latest

# 或禁用 LLM
python scripts/learn_from_session_llm.py --latest --no-llm
```

## 🔮 未来改进

### 已实现 ✅
- ✅ 从 trace.jsonl 提取工具调用序列
- ✅ 识别成功/失败模式
- ✅ 写入记忆文件
- ✅ LLM 智能去重
- ✅ LLM 质量评估

### 进行中 ⏳
- ⏳ LLM 生成有意义的总结
- ⏳ 自动生成 skill 文件
- ⏳ 参数模式提取

### 规划中 🔮
- 🔮 多 session 聚合分析
- 🔮 A/B 测试对比效果
- 🔮 自动优化工具选择
- 🔮 技能版本管理

## 💰 成本分析

### LLM 调用频率
- 每个 session: 1-2 次调用
- 批量 10 个 session: ~4 次调用

### 成本估算（DeepSeek）
- 单次调用: ~0.0005 元
- 每个 session: ~0.001 元
- 每天 10 个 session: ~0.01 元
- 每月: ~0.3 元

**结论**: 成本极低，完全可接受

## 🎓 核心价值

### 解决的问题
1. ❌ **重复记录** → ✅ LLM 智能去重
2. ❌ **质量参差** → ✅ LLM 评估价值
3. ❌ **描述泛化** → ✅ LLM 生成总结
4. ❌ **无法学习** → ✅ 持续自我优化

### 带来的价值
1. ✅ **减少试错**: 从历史成功模式中学习
2. ✅ **提高效率**: 下次遇到类似任务直接使用
3. ✅ **知识沉淀**: 经验持久化到记忆文件
4. ✅ **自我进化**: 越用越聪明

## 🤝 贡献

欢迎提交 Issue 和 PR！

## 📄 许可

MIT License

---

**最后更新**: 2026-03-14
**版本**: v1.0
**作者**: AI Development Team
