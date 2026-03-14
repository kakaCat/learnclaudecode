"""
记忆工具 - memory_write 和 memory_search

参考 s06_intelligence.py 的工具设计，通过 session 实现记忆的写入和搜索。
"""
from backend.app.tools.base import tool
from backend.app.session import get_store

__tool_config__ = {
    "tags": ["main", "team"],
    "category": "execution",
    "enabled": False 
} 

@tool()
def memory_write(content: str, category: str = "general") -> str:
    """
    Save an important fact or observation to memory (auto-layered storage).

    Args:
        content: The fact or observation to remember
        category: Memory category (determines storage location)
            - "session" or "general": Temporary session info (current conversation only)
            - "preference": User preferences (persistent across sessions)
            - "architecture": Project architecture/patterns (persistent across sessions)
            - "tool": Tool usage tips/patterns (persistent across sessions)

    Returns:
        Operation result message

    Examples:
        memory_write("User prefers concise code", "preference")
        memory_write("Project uses FastAPI + LangChain", "architecture")
        memory_write("Found agent.py in backend/app/", "session")
    """
    store = get_store()
    return store.write_memory(content, category)



@tool()
def memory_append(content: str, category: str = "general") -> str:
    """
    Append content to an existing memory entry (for incremental memory building).

    Args:
        content: Content to append
        category: Memory category (same as memory_write)

    Returns:
        Operation result message
    """
    store = get_store()
    return store.append_memory(content, category)


@tool()
def memory_search(query: str, top_k: int = 5) -> str:
    """
    Search stored memories for relevant information, ranked by similarity.
    Uses hybrid search (keyword + vector + temporal decay + MMR reranking).

    Args:
        query: Search query
        top_k: Maximum number of results (default: 5)

    Returns:
        Search results formatted as text
    """
    store = get_store()
    results = store.hybrid_search_memory(query, top_k)

    if not results:
        return "No relevant memories found."

    lines = []
    for r in results:
        lines.append(f"[{r['path']}] (score: {r['score']}) {r['snippet']}")

    return "\n".join(lines)


@tool() 
def memory_deprecate(content: str, reason: str, category: str = "general") -> str:
    """
    Mark a memory as deprecated/obsolete and save the reason.

    Use this when you discover that a previously saved memory is:
    - Outdated (e.g., "Tool X was removed in v2.0")
    - Incorrect (e.g., "Previous assumption about API was wrong")
    - Superseded (e.g., "New approach replaces old pattern")

    Args:
        content: The memory content to deprecate (or description of it)
        reason: Why this memory is deprecated
        category: Memory category (same as memory_write)

    Returns:
        Operation result message

    Examples:
        memory_deprecate("curl tool for HTTP requests", "curl_tool.py was deleted, use requests library instead", "tool")
        memory_deprecate("spawn_subagent returns raw output", "Now returns structured JSON with status/data_count", "architecture")
    """
    store = get_store()
    deprecated_entry = f"[DEPRECATED] {content}\nReason: {reason}\nDeprecated at: {store._get_timestamp()}"
    return store.write_memory(deprecated_entry, category)

