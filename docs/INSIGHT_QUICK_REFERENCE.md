# Trace Insight 快速参考

## 🎯 三个命令速查

```bash
/insight      # 性能分析（免费、秒级）
/insight-llm  # 质量分析 - 当前 session（消耗 token）
/insight-all  # 质量分析 - 选择 session（消耗 token）
```

## 📊 功能对比

| 特性 | /insight | /insight-llm | /insight-all |
|------|----------|--------------|--------------|
| **分析方式** | 规则算法 | LLM 分析 | LLM 分析 |
| **分析对象** | 当前 session | 当前 session | 选择任意 session |
| **速度** | ⚡ 秒级 | 🐌 分钟级 | 🐌 分钟级 |
| **成本** | 💰 免费 | 💸 消耗 token | 💸 消耗 token |
| **分析内容** | 性能指标 | 调用质量 | 调用质量 |

## 🚀 使用场景

### /insight - 日常快速检查
```bash
agent >> /insight

✅ 适用场景：
- 每次任务后快速检查
- 识别性能瓶颈
- 查看工具使用统计
- 获取基础优化建议

❌ 不适用：
- 需要深度分析决策质量
- 需要提示词优化建议
- 需要分析历史 session
```

### /insight-llm - 深度质量分析
```bash
agent >> /insight-llm

✅ 适用场景：
- 发现性能问题后深度分析
- 评估 LLM 决策质量
- 获取提示词优化建议
- 需要具体改进措施

❌ 不适用：
- 只需要快速性能检查
- 需要分析历史 session
- 预算有限（消耗 token）
```

### /insight-all - 历史对比分析
```bash
agent >> /insight-all

✅ 适用场景：
- 对比优化前后效果
- 批量分析历史问题
- 找出共性问题
- 建立优化档案

❌ 不适用：
- 只需要分析当前 session
- 没有历史 session
- 预算有限（消耗 token）
```

## 💡 推荐工作流

### 工作流 1: 日常开发
```bash
1. 执行任务
2. /insight          # 快速检查
3. 如有问题 → /insight-llm  # 深度分析
4. 应用优化
5. 验证效果 → /insight
```

### 工作流 2: 每周优化
```bash
1. /insight-all      # 选择本周 session
2. 记录问题
3. 总结共性
4. 制定优化计划
5. 下周验证
```

### 工作流 3: 重大优化
```bash
1. /insight-all      # 优化前基线
2. 应用优化
3. /insight-all      # 优化后对比
4. 计算改进幅度
5. 文档化经验
```

## 📈 分析内容

### /insight 输出
```
📊 摘要
  运行次数、总耗时、工具调用

⚡ 性能分析
  最慢的运行

🔥 瓶颈分析
  时间分布（子 Agent、LLM、其他）

🔧 工具使用
  工具调用统计、成功率

💡 优化建议
  基于规则的建议
```

### /insight-llm 输出
```
📋 每个运行的分析
  1. 决策质量
  2. 效率分析
  3. 响应质量
  4. 提示词优化
  5. 优化建议

💡 总体优化建议
  3-5 条具体建议
```

## ⚡ 快速决策

```
需要快速检查？
  → /insight

发现性能问题？
  → /insight-llm

需要对比历史？
  → /insight-all

预算有限？
  → 只用 /insight

需要深度优化？
  → /insight + /insight-llm

需要建立档案？
  → /insight-all
```

## 🎓 学习路径

### 第 1 天：熟悉基础
```bash
1. 执行几个任务
2. 运行 /insight
3. 理解输出内容
```

### 第 2 天：深度分析
```bash
1. 运行 /insight-llm
2. 理解 LLM 分析
3. 应用优化建议
```

### 第 3 天：历史对比
```bash
1. 运行 /insight-all
2. 选择不同 session
3. 对比分析结果
```

### 第 4 天：建立流程
```bash
1. 制定日常检查流程
2. 建立优化档案
3. 定期回顾改进
```

## 💰 成本估算

### /insight
- 成本：免费
- 时间：< 1 秒

### /insight-llm
- 成本：约 4000-5000 tokens
- 时间：30-60 秒
- 费用：
  - DeepSeek: ¥0.01-0.02
  - Claude: $0.02-0.05

### /insight-all
- 成本：同 /insight-llm
- 时间：30-60 秒
- 费用：同 /insight-llm

## 🔗 相关命令

```bash
/sessions    # 查看所有 session
/compact     # 压缩对话历史
/tasks       # 查看任务列表
/team        # 查看团队状态
```

## 📚 详细文档

- [INSIGHT_WORKFLOW.md](INSIGHT_WORKFLOW.md) - 完整使用流程
- [INSIGHT_USAGE.md](INSIGHT_USAGE.md) - /insight 详细说明
- [LLM_INSIGHT_USAGE.md](LLM_INSIGHT_USAGE.md) - /insight-llm 详细说明
- [INSIGHT_ALL_USAGE.md](INSIGHT_ALL_USAGE.md) - /insight-all 详细说明

---

**提示：** 将此文档保存为书签，随时查阅！
