"""
compaction.py - 三层上下文压缩流水线

    每次 run() 执行时：
    +------------------+
    | history 消息列表  |
    +------------------+
            |
            v
    [第一层: micro_compact]        （静默，每次执行）
      将最近 3 条以外的 ToolMessage 内容
      替换为 "[Previous: used {tool_name}]"
            |
            v
    [检查: tokens > 50000?]
       |               |
       否              是
       |               |
       v               v
    继续        [第二层: auto_compact]
                  保存完整对话记录到 .transcripts/
                  让 LLM 总结对话内容。
                  用 [summary] 替换所有消息。
                        |
                        v
                [第三层: compact 工具]
                  模型调用 compact -> 在 run() 后触发。
                  与自动压缩相同，由手动触发。
"""

import json
from pathlib import Path

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

THRESHOLD = 50000
KEEP_RECENT = 3


def estimate_tokens(history: list, llm=None) -> int:
    """通过 LLM 的分词器估算 token 数，若不可用则按每 token 约 4 个字符估算。"""
    if llm is not None:
        try:
            return llm.get_num_tokens_from_messages(history)
        except NotImplementedError:
            pass
    return len(str(history)) // 4


def micro_compact(history: list) -> None:
    """第一层：将旧的 ToolMessage 内容替换为占位符（原地修改）。"""
    tool_msgs = [(i, m) for i, m in enumerate(history) if isinstance(m, ToolMessage)]
    if len(tool_msgs) <= KEEP_RECENT:
        return
    # Build tool_id -> tool_name map from AIMessages
    tool_name_map = {}
    for m in history:
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                tool_name_map[tc["id"]] = tc["name"]
    # Replace all but the last KEEP_RECENT tool results
    for idx, msg in tool_msgs[:-KEEP_RECENT]:
        if len(str(msg.content)) > 100:
            tool_name = tool_name_map.get(msg.tool_call_id, "unknown")
            history[idx] = ToolMessage(
                content=f"[Previous: used {tool_name}]",
                tool_call_id=msg.tool_call_id,
            )


def auto_compact(history: list, llm) -> list:
    """第二层 & 第三层：保存对话记录，用 LLM 总结，返回压缩后的历史记录。"""
    from backend.app.session import get_session_dir
    session_dir = get_session_dir()
    transcript_path = session_dir / "transcript.jsonl"
    with open(transcript_path, "w") as f:
        for m in history:
            f.write(json.dumps({"role": type(m).__name__, "content": str(m.content)}) + "\n")
    # Ask LLM to summarize
    conversation_text = "\n".join(
        f"{type(m).__name__}: {str(m.content)[:500]}" for m in history
    )[:80000]
    summary = llm.invoke([HumanMessage(content=
        "请总结这段对话以便后续继续。包含：1) 已完成的工作，2) 当前状态，3) 关键决策。"
        "简明扼要，但保留关键细节。\n\n" + conversation_text
    )]).content
    # Replace all messages with compressed summary
    return [
        HumanMessage(content=f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}"),
        AIMessage(content="明白。我已获取摘要中的上下文，继续执行。"),
    ]
