"""
Direct Loop 函数实现 - 从 agent_runner.py 提取

核心模式：
    while tool_calls exist:
        response = LLM(messages, tools)
        execute tools
        append results

包含的函数：
- execute_direct_loop: 主循环
- validate_and_fix_messages: 验证消息结构
- execute_tool: 执行工具（支持 fallback）
"""
import json
from typing import List, Tuple
from langchain_core.messages import ToolMessage

from backend.app.memory.compaction import micro_compact, auto_compact, estimate_tokens
from backend.app.core.execution.config import CONFIG


async def execute_direct_loop(
    context,
    messages: List,
    guard_manager,
    langchain_callback=None
) -> Tuple[str, List[dict]]:
    """
    执行直接循环

    Args:
        context: Agent 上下文
        messages: 消息列表
        guard_manager: 守卫管理器
        langchain_callback: LangChain Callback Handler

    Returns:
        (output, tool_calls_data)
    """
    # 绑定工具到 LLM
    llm_with_tools = context.llm.bind_tools(context.get_tools())

    output = ""
    tool_calls_data = []
    loop_count = 0

    print(f"\n🔄 开始直接循环...")
    print(f"📋 工具数量: {len(context.get_tools())}")
    print(f"💬 初始消息数: {len(messages)}")

    # 核心循环
    while True:
        loop_count += 1
        print(f"\n--- Loop {loop_count} ---")

        # 检查手动压缩请求
        from backend.app.memory.compact import was_compact_requested
        if was_compact_requested():
            print(f"🗜️  手动触发压缩...")
            messages[:] = auto_compact(messages, context.llm)

        # 自动压缩
        micro_compact(messages)
        tokens = estimate_tokens(messages, context.llm)
        if tokens > CONFIG.COMPRESSION_THRESHOLD:
            print(f"⚠️  Context at {tokens} tokens, auto-compacting...")
            messages[:] = auto_compact(messages, context.llm)

        # 验证消息结构
        _validate_and_fix_messages(messages)

        # 1. 调用 LLM
        print(f"🤖 调用 LLM (messages: {len(messages)})")
        response = llm_with_tools.invoke(
            messages,
            config={"callbacks": [langchain_callback]} if langchain_callback else {}
        )
        messages.append(response)

        # 2. 检查工具调用
        tool_calls = getattr(response, "tool_calls", None)

        if not tool_calls:
            output = response.content or ""
            print(f"✅ LLM 返回最终答案 (长度: {len(output)})")

            # 检查守卫违规
            injected = guard_manager.check_and_inject_after_llm(response, messages)
            if injected:
                print(f"⚠️  守卫检测到违规，重新循环")

                if langchain_callback and langchain_callback.enable_tracer:
                    warning_message = messages[-1].content if messages else ""
                    langchain_callback.tracer.emit(
                        f"{langchain_callback.agent_type}.guard_violation",
                        loop_count=loop_count,
                        reason="承诺调用工具但未调用",
                        warning_injected=warning_message[:500],
                        messages_count=len(messages)
                    )

                continue
            break

        # 3. 执行工具调用
        print(f"🔧 执行 {len(tool_calls)} 个工具调用")

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            print(f"  → {tool_name}({list(tool_args.keys())})")
            tool_calls_data.append({"name": tool_name, "args": tool_args})

            # 执行工具
            tool_result = await _execute_tool(
                context, tool_name, tool_args, langchain_callback
            )
            print(f"  ← 结果: {tool_result[:100]}...")

            # 追加工具结果
            messages.append(ToolMessage(
                content=tool_result,
                tool_call_id=tool_id,
                name=tool_name
            ))

            # 更新守卫状态
            guard_manager.on_tool_call(tool_name)

    print(f"\n✅ 循环结束 (总计 {loop_count} 轮, {len(tool_calls_data)} 次工具调用)\n")
    return output, tool_calls_data


def _validate_and_fix_messages(messages: List):
    """验证并修复消息结构"""
    i = 0
    while i < len(messages):
        msg = messages[i]
        tool_calls = getattr(msg, "tool_calls", None)

        if tool_calls:
            tool_call_ids = {tc["id"] for tc in tool_calls}
            j = i + 1
            found_ids = set()

            while j < len(messages) and isinstance(messages[j], ToolMessage):
                found_ids.add(messages[j].tool_call_id)
                j += 1

            if tool_call_ids != found_ids:
                print(f"⚠️  修复消息结构：删除不匹配的 tool_calls 消息")
                messages.pop(i)
                continue

        i += 1


async def _execute_tool(context, tool_name: str, tool_args: dict, langchain_callback=None) -> str:
    """执行单个工具，支持 fallback"""
    from backend.app.core.execution.tool_fallback import get_fallback_registry

    tools = context.get_tools()

    # 查找工具
    tool = None
    for t in tools:
        if t.name == tool_name:
            tool = t
            break

    if tool is None:
        return f"Error: Tool '{tool_name}' not found"

    try:
        # 执行工具
        if langchain_callback:
            result = tool.invoke(tool_args, config={"callbacks": [langchain_callback]})
        else:
            result = tool.invoke(tool_args)

        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        error_msg = str(e)
        print(f"  ⚠️  工具 {tool_name} 执行失败: {error_msg}")

        # 查找 fallback
        registry = get_fallback_registry()
        fallback_info = registry.get_fallback(tool_name, e)

        if fallback_info:
            fallback_name, transform_fn = fallback_info
            print(f"  🔄 尝试替代工具: {fallback_name}")

            fallback_tool = None
            for t in tools:
                if t.name == fallback_name:
                    fallback_tool = t
                    break

            if fallback_tool:
                try:
                    new_args = transform_fn(tool_args, e)
                    print(f"  📝 转换参数: {list(new_args.keys())}")

                    if langchain_callback:
                        result = fallback_tool.invoke(new_args, config={"callbacks": [langchain_callback]})
                    else:
                        result = fallback_tool.invoke(new_args)

                    print(f"  ✅ 替代工具执行成功")
                    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                except Exception as fallback_error:
                    print(f"  ❌ 替代工具也失败: {fallback_error}")
                    return f"Error: {tool_name} failed ({error_msg}), fallback {fallback_name} also failed ({fallback_error})"

        return f"Error executing tool: {error_msg}"
