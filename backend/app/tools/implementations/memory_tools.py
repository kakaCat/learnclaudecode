"""
记忆工具 - memory_write 和 memory_search

参考 s06_intelligence.py 的工具设计，通过 session 实现记忆的写入和搜索。
"""
from langchain_core.tools import tool
from backend.app.session import get_store


@tool
def memory_write(content: str, category: str = "general") -> str:
    """
    Save an important fact or observation to long-term memory.
    Use when you learn something worth remembering about the user or context.

    Args:
        content: The fact or observation to remember
        category: Category (preference, fact, context, etc.)

    Returns:
        Operation result message
    """
    store = get_store()
    return store.write_memory(content, category)


@tool
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
