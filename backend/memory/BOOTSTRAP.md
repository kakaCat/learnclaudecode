# Bootstrap 启动配置

## 加载顺序

1. IDENTITY.md - 身份定义
2. SOUL.md - 人格特征
3. TOOLS.md - 工具使用指南
4. USER.md - 用户信息
5. HEARTBEAT.md - 心跳配置
6. BOOTSTRAP.md - 本文件
7. AGENTS.md - Agent 配置
8. MEMORY.md - 长期记忆

## 加载模式

### full (主 Agent)
- 加载所有 8 个文件
- 完整的系统提示词
- 所有工具和能力

### minimal (子 Agent)
- 仅加载 AGENTS.md, TOOLS.md
- 精简的系统提示词
- 受限的工具集

### none (最小化)
- 不加载任何 Bootstrap 文件
- 仅核心指令
- 基础工具

## 文件限制

- 单个文件最大: 20,000 字符
- 总字符数上限: 150,000 字符
- 超长文件自动截断（保留头部）

## 初始化流程

1. 检查 `.bootstrap/` 目录是否存在
2. 按顺序加载文件（跳过不存在的文件）
3. 应用文件截断规则
4. 检查总字符数限制
5. 组装到系统提示词的对应层级

## 更新机制

- Bootstrap 文件在 agent 启动时加载一次
- 运行时不会重新加载
- 修改后需要重启 agent 生效
