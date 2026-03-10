"""
统一的记忆管理系统

两层存储：
1. 全局记忆（.memory/）- SOUL.md, IDENTITY.md, TOOLS.md, USER.md, MEMORY.md 等
2. 会话记忆（workspace/memory/）- MEMORY.md + daily/{date}.jsonl
"""
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .constants import MEMORY_DIR

# 全局记忆文件列表
GLOBAL_MEMORY_FILES = [
    "SOUL.md",
    "IDENTITY.md",
    "TOOLS.md",
    "USER.md",
    "HEARTBEAT.md",
    "BOOTSTRAP.md",
    "AGENTS.md",
    "MEMORY.md",
]

MAX_FILE_CHARS = 20000


class GlobalMemoryLoader:
    """全局记忆文件加载器"""

    def __init__(self, memory_dir: Path = MEMORY_DIR):
        self.memory_dir = memory_dir
        self._cache: Dict[str, str] = {}

    def load_file(self, name: str) -> str:
        """加载单个文件（带缓存）"""
        if name in self._cache:
            return self._cache[name]

        path = self.memory_dir / name
        if not path.is_file():
            return ""
        try:
            content = path.read_text(encoding="utf-8")
            if len(content) > MAX_FILE_CHARS:
                content = content[:MAX_FILE_CHARS] + f"\n\n[... truncated at {MAX_FILE_CHARS} chars ...]"

            self._cache[name] = content
            return content
        except Exception:
            return ""

    def load_soul(self) -> str:
        """加载 SOUL.md 文件"""
        return self.load_file("SOUL.md").strip()

    def update_file(self, name: str, content: str) -> bool:
        """更新文件内容并清除缓存"""
        path = self.memory_dir / name
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self._cache.pop(name, None)
            return True
        except Exception:
            return False

    def append_to_memory(self, content: str) -> bool:
        """追加内容到全局 MEMORY.md"""
        current = self.load_file("MEMORY.md")
        updated = f"{current}\n\n{content}".strip() if current else content
        return self.update_file("MEMORY.md", updated)

    def load_all(self, mode: str = "full") -> Dict[str, str]:
        """加载全局记忆文件"""
        if mode == "none":
            return {}

        names = ["AGENTS.md", "TOOLS.md"] if mode == "minimal" else GLOBAL_MEMORY_FILES

        result = {}
        for name in names:
            content = self.load_file(name)
            if content:
                result[name] = content

        return result


class MemoryStore:
    """记忆存储管理器"""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.memory_dir = workspace_dir / "memory" / "daily"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._evergreen_cache: str | None = None

    def write_memory(self, content: str, category: str = "general") -> str:
        """写入记忆到每日日志"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.memory_dir / f"{today}.jsonl"

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "content": content,
        }

        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            return f"Memory saved to {today}.jsonl"
        except Exception as exc:
            return f"Error: {exc}"

    def load_evergreen(self) -> str:
        """加载长期记忆（MEMORY.md）带缓存"""
        if self._evergreen_cache is not None:
            return self._evergreen_cache

        path = self.workspace_dir / "MEMORY.md"
        if not path.is_file():
            self._evergreen_cache = ""
            return ""
        try:
            content = path.read_text(encoding="utf-8").strip()
            self._evergreen_cache = content
            return content
        except Exception:
            self._evergreen_cache = ""
            return ""

    def _load_chunks(self) -> List[Dict[str, str]]:
        """加载所有记忆块"""
        chunks = []

        # 加载 MEMORY.md
        evergreen = self.load_evergreen()
        if evergreen:
            for para in evergreen.split("\n\n"):
                para = para.strip()
                if para:
                    chunks.append({"path": "MEMORY.md", "text": para})

        # 加载每日记忆
        if self.memory_dir.is_dir():
            for jf in sorted(self.memory_dir.glob("*.jsonl")):
                try:
                    for line in jf.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        text = entry.get("content", "")
                        if text:
                            cat = entry.get("category", "")
                            label = f"{jf.name}[{cat}]" if cat else jf.name
                            chunks.append({"path": label, "text": text})
                except Exception:
                    continue

        return chunks

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """分词"""
        tokens = re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower())
        return [t for t in tokens if len(t) > 1 or "\u4e00" <= t <= "\u9fff"]

    def search_memory(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """TF-IDF 搜索"""
        chunks = self._load_chunks()
        if not chunks:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        chunk_tokens = [self._tokenize(c["text"]) for c in chunks]

        # 计算 IDF
        df: Dict[str, int] = {}
        for tokens in chunk_tokens:
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1

        n = len(chunks)

        def tfidf(tokens: List[str]) -> Dict[str, float]:
            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            return {
                t: c * (math.log((n + 1) / (df.get(t, 0) + 1)) + 1)
                for t, c in tf.items()
            }

        def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
            common = set(a) & set(b)
            if not common:
                return 0.0
            dot = sum(a[k] * b[k] for k in common)
            na = math.sqrt(sum(v * v for v in a.values()))
            nb = math.sqrt(sum(v * v for v in b.values()))
            return dot / (na * nb) if na and nb else 0.0

        qvec = tfidf(query_tokens)
        scored = []

        for i, tokens in enumerate(chunk_tokens):
            if not tokens:
                continue
            score = cosine(qvec, tfidf(tokens))
            if score > 0.0:
                snippet = chunks[i]["text"]
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                scored.append({
                    "path": chunks[i]["path"],
                    "score": round(score, 4),
                    "snippet": snippet
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def hybrid_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        混合搜索：结合 evergreen 和 daily 记忆

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        return self.search_memory(query, top_k)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        evergreen = self.load_evergreen()
        daily_files = list(self.memory_dir.glob("*.jsonl")) if self.memory_dir.is_dir() else []

        total_entries = 0
        for f in daily_files:
            try:
                total_entries += sum(1 for line in f.read_text(encoding="utf-8").splitlines() if line.strip())
            except Exception:
                pass

        return {
            "evergreen_chars": len(evergreen),
            "daily_files": len(daily_files),
            "daily_entries": total_entries,
        }
