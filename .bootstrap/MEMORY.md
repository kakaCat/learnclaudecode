# 长期记忆

## 项目信息

- 项目名称: learnclaudecode
- 项目类型: AI Agent 学习示例项目
- 技术栈: Python, Anthropic SDK, LangChain, DeepSeek

## 架构特点

- 采用 session 机制管理会话状态
- 支持 Bootstrap 文件加载（SOUL.md, IDENTITY.md 等）
- 实现了混合记忆搜索（TF-IDF + 向量 + 时间衰减 + MMR）
- 系统提示词采用 8 层组装结构

## 开发规范

- 文件超过 200 行时分段写入，每段 ≤150 行
- 写完文件后运行 `python -m py_compile` 验证语法
- 禁止单次 Write 超过 12800 字符
- 升级 agent 时逐模块进行，一次只写一个文件

## 用户偏好

- 不要主动执行 git commit，除非用户明确要求
- 使用中文进行交流和文档编写
- 注重代码质量和架构清晰度
