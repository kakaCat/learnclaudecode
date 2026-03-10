# Agent 任务完成优化总结

## 问题分析

从 `.sessions/20260310_140753/trace.jsonl` 分析，用户要求"制作北京到武汉的旅游计划网页"，但 agent 失败了：

### 失败原因

1. **机票查询失败** - CDPBrowser 第2、3次调用没有实际执行 cdp_browser 工具
2. **没有创建 HTML 文件** - 最后只说"让我创建网页"，但没有调用 write_file
3. **任务执行不完整** - 创建了 todo 但没有执行完所有步骤

### 根本原因

- **CDPBrowser 问题**：没有先检查 CDP 服务是否可用，直接失败
- **执行规则不明确**：agent 不知道"说要做"和"实际做"的区别
- **缺少完成验证**：没有机制确保任务真正完成

## 优化方案

### 1. 添加任务完成强制规则 ✅

**文件**: `backend/memory/TOOLS.md`

**新增内容**:
```markdown
## 任务完成规则（重要）

**禁止只说不做**：
- ❌ 错误："让我创建一个网页" → 然后就结束了
- ✅ 正确："让我创建一个网页" → 立即调用 write_file 创建 HTML

**用户要求"制作网页/生成HTML/创建页面"时**：
1. 必须调用 write_file 工具创建 .html 文件
2. 文件路径使用当前目录或 workspace/
3. 完成后告诉用户文件路径和如何打开
4. 不要只是"计划"或"准备"，必须实际执行
```

**效果**: agent 会明确知道必须调用工具，而不是只说要做

### 2. 优化 CDPBrowser 启动检查 ✅

**文件**: `backend/app/subagents/__init__.py`

**修改内容**:
```python
"## 启动检查（第一步必做）\n"
"1. 先调用 cdp_browser(action='check_health') 检查服务是否可用\n"
"2. 如果不可用，立即返回错误信息和启动命令，不要继续\n"
"3. 如果可用，开始执行任务\n\n"
```

**效果**: CDPBrowser 会先检查 Chrome 是否启动，避免静默失败

### 3. 添加任务完成前自检 ✅

**文件**: `backend/memory/TOOLS.md`

**新增规则**:
```markdown
- **任务完成前自检**：在回复用户前，检查是否真正完成了用户的所有要求，
  如果有未完成的步骤，继续执行而不是只说"让我做X"。
```

**效果**: agent 在回复前会检查是否真正完成任务

## 预期效果

优化后，当用户再次要求"制作旅游计划网页"时：

### 执行流程

1. **收集信息** → CDPBrowser 先检查 Chrome，然后访问网页
2. **创建 HTML** → 立即调用 write_file 创建网页文件
3. **验证完成** → 检查所有步骤是否完成
4. **告知用户** → 提供文件路径和打开方式

### 对比

**优化前**:
```
Turn 5: "让我创建一个完整的5天旅游计划网页"
Turn 6: "现在让我创建网页..." → 结束（没有实际创建）
```

**优化后**:
```
Turn 5: "让我创建网页"
Turn 5: 调用 write_file('travel_plan.html', content)
Turn 5: "✅ 已创建网页：travel_plan.html，在浏览器中打开查看"
```

## 如何验证优化效果

1. 重新运行相同的任务：
   ```bash
   python backend/main.py
   # 输入：给我做一个北京到武汉的旅游计划,明天后5天的,最后用一个网页给我展示
   ```

2. 检查是否生成了 HTML 文件
3. 检查 trace.jsonl 是否有 write_file 调用
4. 检查 CDPBrowser 是否先调用了 check_health

## 其他建议

### 启动 Chrome（如果机票查询需要）

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 --headless --disable-gpu --no-sandbox &

# Linux
google-chrome --remote-debugging-port=9222 --headless --disable-gpu --no-sandbox &
```

### 监控 agent 执行

```bash
# 实时查看 trace
tail -f .sessions/*/trace.jsonl | jq .
```

## 总结

通过这三个优化，agent 现在会：
1. ✅ 实际执行工具调用，而不是只说要做
2. ✅ 检查 CDP 服务可用性，避免静默失败
3. ✅ 完成前自检，确保任务真正完成

这些优化解决了"只说不做"的核心问题。
