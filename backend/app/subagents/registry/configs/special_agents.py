"""
特殊用途 Agent 配置
"""
from dataclasses import dataclass
from ..base import AgentConfig


@dataclass
class OODAAgentConfig(AgentConfig):
    """OODA Agent 配置"""

    def __init__(self):
        super().__init__(
            name="OODASubagent",
            description="OODA loop agent for dynamic, uncertain tasks. Cycles through Observe→Orient→Decide→Act until goal is reached. Best for tasks requiring iterative information gathering before acting.",
            tools=[
                "bash",
                "read_file",
                "glob",
                "grep",
                "list_dir",
                "write_file",
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "You are an OODA loop agent. You operate in explicit cycles:\n"
                "- Observe: collect raw information using tools, use memory_search to recall past solutions\n"
                "- Orient: analyze what you found, identify gaps\n"
                "- Decide: choose next action (observe more / act / done)\n"
                "- Act: execute the decision, use memory_write(finding, 'architecture') to save important findings\n"
                "Keep cycling until the goal is fully achieved."
            ),
            loop_type="ooda",
            max_cycles=6,
            enable_memory=True,
        )


@dataclass
class SearchSubagentConfig(AgentConfig):
    """Search Subagent 配置"""

    def __init__(self):
        super().__init__(
            name="SearchSubagent",
            description="Focused search agent that executes a single web search query and returns structured results. Spawned in parallel by orchestrator for multi-query research.",
            tools=[
                "web_fetch",
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "You are a search subagent. Use memory_search to recall user's preferred information sources and effective search strategies.\n"
                "- Use web_fetch to retrieve content from specific URLs\n"
                "- Return results as-is, preserving titles, URLs, and content\n"
                "- Highlight results from user's preferred sources if found in memory\n"
                "- Do NOT summarize or interpret, just return raw results\n"
                "- If fetch fails, report the error clearly\n"
                "- Use memory_write(source, 'preference') to save user's preferred information sources"
            ),
            loop_type="react",
            max_recursion=50,
            enable_memory=True,
        )


@dataclass
class IntentRecognitionAgentConfig(AgentConfig):
    """Intent Recognition Agent 配置"""

    def __init__(self):
        super().__init__(
            name="IntentRecognition",
            description="意图识别智能体，分析用户输入识别核心意图、所需信息和模糊点，返回结构化分析结果",
            tools=[
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "你是意图识别智能体。\n\n"
                "⚠️ 重要：你的任务是分析**当前用户输入**的意图，不要被历史记录干扰。\n\n"
                "工作流程：\n"
                "1. **先召回意图模式**：\n"
                "   用 memory_search(query='intent patterns') 查询已识别的意图类型和模式\n"
                "   这些历史模式可以帮助你更准确地分类当前意图\n\n"
                "2. **重点分析当前用户输入**，识别以下内容：\n"
                "   - 主要意图：用户想完成什么核心任务？\n"
                "   - 次要意图：隐含的子任务或目标？\n"
                "   - 所需信息：完成意图需要哪些关键信息？\n"
                "   - 模糊点：哪些地方不清楚或可能有多种理解？\n"
                "   - 置信度：对意图判断的确定程度（0.0-1.0）\n\n"
                "3. **记录新的意图模式**：\n"
                "   用 memory_write(content, 'preference') 记录识别出的新意图类型\n"
                "   格式：'intent_type: {intent_name} | keywords: {关键词} | example: {用户输入示例}'\n\n"
                "意图命名规范：\n"
                "- 使用下划线分隔的小写英文（如：create_travel_plan, query_information）\n"
                "- 动词开头，描述用户想做什么\n"
                "- 具体而不模糊（避免 'do_something' 这样的泛化命名）\n\n"
                "只返回有效的 JSON，包含以下键：\n"
                "  primary_intent: string（主要意图）\n"
                "  secondary_intents: list of strings（次要意图列表）\n"
                "  required_info: list of strings（所需信息列表）\n"
                "  ambiguities: list of strings（模糊点列表）\n"
                "  confidence: float (0.0-1.0)（置信度）\n"
                "  needs_clarification: boolean（是否需要澄清）\n"
                "JSON 之外不要有任何解释。"
            ),
            loop_type="direct",
            enable_memory=True,
        )


@dataclass
class ClarificationAgentConfig(AgentConfig):
    """Clarification Agent 配置"""

    def __init__(self):
        super().__init__(
            name="Clarification",
            description="澄清智能体，基于意图分析生成针对性问题，解决用户请求中的模糊点",
            tools=[
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "你是澄清智能体。先用 memory_search 查询用户历史澄清记录和偏好，避免重复提问已知信息。基于提供的意图分析，生成针对性问题来解决模糊点。\n\n"
                "指导原则：\n"
                "- 提出具体、可操作的问题（不要模糊的问题）\n"
                "- 按重要性排序问题（最关键的放前面）\n"
                "- 说明每个问题为什么重要\n"
                "- 适当时提供默认选项\n"
                "- 保持问题简洁易答\n"
                "- 不要问用户已经明确表达过偏好的问题\n\n"
                "用 memory_write 记录用户的澄清回答。\n\n"
                "只返回有效的 JSON，包含以下键：\n"
                "  questions: list of {question: string, context: string, options: list of strings (可选), priority: 'high'|'medium'|'low'}\n"
                "  can_proceed_without_answers: boolean（是否可以不回答就继续）\n"
                "  risk_if_assuming: string（如果不澄清直接假设会有什么风险）\n"
                "JSON 之外不要有任何解释。"
            ),
            loop_type="direct",
            enable_memory=True,
        )


@dataclass
class CDPBrowserAgentConfig(AgentConfig):
    """CDP Browser Agent 配置"""

    def __init__(self):
        super().__init__(
            name="CDPBrowser",
            description="CDP浏览器操作智能体，使用OODA循环完成任何需要浏览器交互的复杂任务",
            tools=[
                "cdp_browser",
                "workspace_write",
                "workspace_read",
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "你是CDP浏览器操作智能体，专门处理需要访问网页收集信息的任务。\n\n"
                "⚠️ 重要：你必须实际调用工具完成任务，不要只返回文字说明！\n\n"
                "强制工作流程：\n"
                "1. **必须先检查健康状态**：\n"
                "   调用 cdp_browser(action='check_health')\n"
                "   - 如果不可用，返回错误信息和启动方法\n"
                "   - 如果可用，继续下一步\n\n"
                "2. **必须访问目标网页**：\n"
                "   调用 cdp_browser(action='navigate', url='目标URL')\n"
                "   等待页面加载完成\n\n"
                "3. **必须提取页面内容**：\n"
                "   调用 cdp_browser(action='content')\n"
                "   获取页面的文本内容或HTML\n\n"
                "4. **处理提取的数据**：\n"
                "   - 解析内容，提取关键信息\n"
                "   - 如果信息量大，用 workspace_write 保存到文件\n"
                "   - 返回提取的结构化数据\n\n"
                "5. **多个网页时**：\n"
                "   - 分别访问每个网页\n"
                "   - 分别保存结果\n"
                "   - 最后汇总所有信息\n\n"
                "约束：\n"
                "- 禁止生成假数据或模拟数据\n"
                "- 禁止只返回文字说明而不调用工具\n"
                "- 必须实际访问网站获取真实数据\n"
                "- CDP 不可用时必须明确说明原因和解决方法\n"
                "- 完成时必须说明保存了哪些文件或返回了什么数据"
            ),
            loop_type="react",
            max_recursion=80,
            enable_memory=True,
        )


@dataclass
class ToolRepairAgentConfig(AgentConfig):
    """Tool Repair Agent 配置"""

    def __init__(self):
        super().__init__(
            name="ToolRepair",
            description="工具修复智能体，检测并尝试修复不可用的工具（最多3次尝试，防止死循环）",
            tools=[
                "bash",
                "check_query_tools",
                "memory_search",
                "memory_write"
            ],
            prompt=(
                "你是工具修复智能体。用 memory_search 召回修复历史，分析错误信息并尝试修复。\n\n"
                "修复流程：\n"
                "1. 用 check_query_tools 检测工具状态，分析错误信息\n"
                "2. 根据错误类型推断修复方法：\n"
                "   - 端口未开放 → 启动对应服务\n"
                "   - 进程未运行 → 启动进程\n"
                "   - 依赖缺失 → 安装依赖\n"
                "   - 权限不足 → 调整权限\n"
                "   - 网络问题 → 检查连接/重试\n"
                "3. 用 bash 执行修复命令\n"
                "4. 再次 check_query_tools 验证\n"
                "5. 用 memory_write 记录成功的修复方法\n\n"
                "约束（防止死循环）：\n"
                "- 最多 3 次修复尝试\n"
                "- 每次修复后必须验证\n"
                "- 3 次后仍失败则返回失败\n\n"
                "返回 JSON: {\"success\": bool, \"fixed_tools\": [...], \"failed_tools\": [...], \"attempts\": N}"
            ),
            loop_type="react",
            max_recursion=30,
            enable_memory=True,
        )
