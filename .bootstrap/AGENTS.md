# Agent 配置

## 主 Agent

- **名称**: main
- **类型**: 全功能 CLI Agent
- **模式**: full (加载所有 Bootstrap 文件)
- **能力**: 文件操作、命令执行、子 agent 派发、记忆管理

## 子 Agent 类型

### Explore
- **用途**: 只读探索，查找文件和搜索内容
- **模式**: minimal
- **工具**: glob, grep, read_file, list_dir

### Plan
- **用途**: 规划复杂任务的实现策略
- **模式**: minimal
- **输出**: 任务拆分、文件清单、实现步骤

### Reflect
- **用途**: 验证输出质量
- **模式**: minimal
- **输出**: verdict (PASS/NEEDS_REVISION), suggestion

### Reflexion
- **用途**: 深度改进和优化
- **模式**: minimal
- **流程**: Responder 收集上下文 → Revisor 生成改进版

### general-purpose
- **用途**: 全功能实现
- **模式**: full
- **能力**: 完整的文件操作和命令执行

### IntentRecognition
- **用途**: 识别用户意图
- **模式**: minimal
- **输出**: intent, confidence, missing_info, needs_clarification

### Clarification
- **用途**: 生成澄清问题
- **模式**: minimal
- **输出**: 针对性问题列表

## Agent 生命周期

1. **创建**: 通过 Task 工具派发
2. **执行**: 独立运行，完成指定任务
3. **返回**: 将结果返回给父 agent
4. **销毁**: 任务完成后自动清理
