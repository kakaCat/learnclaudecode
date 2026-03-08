"""
记忆存储系统

参考 s06_intelligence.py 的 MemoryStore 设计：
- 两层存储：MEMORY.md（长期事实）+ daily/*.jsonl（每日日志）
- TF-IDF + 余弦相似度搜索
- 混合搜索：关键词搜索 + 向量搜索 + 时间衰减 + MMR 重排序
"""
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class MemoryStore:
    """
    记忆存储管理器

    两层存储结构：
    1. MEMORY.md - 长期事实（手动维护）
    2. daily/{date}.jsonl - 每日日志（通过工具自动写入）

    搜索方式：
    - search_memory: 简单 TF-IDF 搜索
    - hybrid_search: 混合搜索（关键词 + 向量 + 时间衰减 + MMR）
    """

    def __init__(self, workspace_dir: Path):
        """
        Args:
            workspace_dir: session workspace 目录
        """
        self.workspace_dir = workspace_dir
        self.memory_dir = workspace_dir / "memory" / "daily"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def write_memory(self, content: str, category: str = "general") -> str:
        """
        写入记忆到每日日志

        Args:
            content: 记忆内容
            category: 分类（preference, fact, context 等）

        Returns:
            操作结果消息
        """
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
            return f"Memory saved to {today}.jsonl ({category})"
        except Exception as exc:
            return f"Error writing memory: {exc}"

    def load_evergreen(self) -> str:
        """
        加载长期记忆（MEMORY.md）

        Returns:
            MEMORY.md 内容，文件不存在返回空字符串
        """
        path = self.workspace_dir / "MEMORY.md"
        if not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _load_all_chunks(self) -> List[Dict[str, str]]:
        """
        加载所有记忆并拆分为块

        Returns:
            块列表，每个块包含 path 和 text
        """
        chunks: List[Dict[str, str]] = []

        # 1. 加载长期记忆，按段落拆分
        evergreen = self.load_evergreen()
        if evergreen:
            for para in evergreen.split("\n\n"):
                para = para.strip()
                if para:
                    chunks.append({"path": "MEMORY.md", "text": para})

        # 2. 加载每日记忆，每条 JSONL 记录作为一个块
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
                            label = f"{jf.name} [{cat}]" if cat else jf.name
                            chunks.append({"path": label, "text": text})
                except Exception:
                    continue

        return chunks

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """
        分词：小写英文 + 单个 CJK 字符

        Args:
            text: 原始文本

        Returns:
            token 列表
        """
        tokens = re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower())
        # 过滤短 token（保留单个 CJK 字符）
        return [t for t in tokens if len(t) > 1 or "\u4e00" <= t <= "\u9fff"]

    def search_memory(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        TF-IDF + 余弦相似度搜索

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            搜索结果列表，每个结果包含 path, score, snippet
        """
        chunks = self._load_all_chunks()
        if not chunks:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        chunk_tokens = [self._tokenize(c["text"]) for c in chunks]

        # 计算文档频率
        df: Dict[str, int] = {}
        for tokens in chunk_tokens:
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1

        n = len(chunks)

        def tfidf(tokens: List[str]) -> Dict[str, float]:
            """计算 TF-IDF 向量"""
            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            return {
                t: c * (math.log((n + 1) / (df.get(t, 0) + 1)) + 1)
                for t, c in tf.items()
            }

        def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
            """计算余弦相似度"""
            common = set(a) & set(b)
            if not common:
                return 0.0
            dot = sum(a[k] * b[k] for k in common)
            na = math.sqrt(sum(v * v for v in a.values()))
            nb = math.sqrt(sum(v * v for v in b.values()))
            return dot / (na * nb) if na and nb else 0.0

        qvec = tfidf(query_tokens)
        scored: List[Dict[str, Any]] = []

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

    # ========== 混合搜索增强 ==========

    @staticmethod
    def _hash_vector(text: str, dim: int = 64) -> List[float]:
        """
        模拟向量嵌入（基于哈希的随机投影）

        不需要外部 API，用于演示第二搜索通道的模式。

        Args:
            text: 文本
            dim: 向量维度

        Returns:
            归一化向量
        """
        tokens = MemoryStore._tokenize(text)
        vec = [0.0] * dim
        for token in tokens:
            h = hash(token)
            for i in range(dim):
                bit = (h >> (i % 62)) & 1
                vec[i] += 1.0 if bit else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def _vector_cosine(a: List[float], b: List[float]) -> float:
        """计算向量余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na and nb else 0.0

    @staticmethod
    def _jaccard_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
        """计算 Jaccard 相似度"""
        set_a, set_b = set(tokens_a), set(tokens_b)
        inter = len(set_a & set_b)
        union = len(set_a | set_b)
        return inter / union if union else 0.0

    def _vector_search(
        self, query: str, chunks: List[Dict[str, str]], top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索"""
        q_vec = self._hash_vector(query)
        scored = []
        for chunk in chunks:
            c_vec = self._hash_vector(chunk["text"])
            score = self._vector_cosine(q_vec, c_vec)
            if score > 0.0:
                scored.append({"chunk": chunk, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _keyword_search(
        self, query: str, chunks: List[Dict[str, str]], top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """关键词搜索（复用 TF-IDF）"""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        chunk_tokens = [self._tokenize(c["text"]) for c in chunks]
        n = len(chunks)

        df: Dict[str, int] = {}
        for tokens in chunk_tokens:
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1

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
                scored.append({"chunk": chunks[i], "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _merge_hybrid_results(
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """合并向量和关键词搜索结果"""
        merged: Dict[str, Dict[str, Any]] = {}

        for r in vector_results:
            key = r["chunk"]["text"][:100]
            merged[key] = {"chunk": r["chunk"], "score": r["score"] * vector_weight}

        for r in keyword_results:
            key = r["chunk"]["text"][:100]
            if key in merged:
                merged[key]["score"] += r["score"] * text_weight
            else:
                merged[key] = {"chunk": r["chunk"], "score": r["score"] * text_weight}

        result = list(merged.values())
        result.sort(key=lambda x: x["score"], reverse=True)
        return result

    @staticmethod
    def _temporal_decay(
        results: List[Dict[str, Any]], decay_rate: float = 0.01
    ) -> List[Dict[str, Any]]:
        """应用时间衰减"""
        now = datetime.now(timezone.utc)
        for r in results:
            path = r["chunk"].get("path", "")
            age_days = 0.0
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", path)
            if date_match:
                try:
                    chunk_date = datetime.strptime(
                        date_match.group(1), "%Y-%m-%d"
                    ).replace(tzinfo=timezone.utc)
                    age_days = (now - chunk_date).total_seconds() / 86400.0
                except ValueError:
                    pass
            r["score"] *= math.exp(-decay_rate * age_days)
        return results

    @staticmethod
    def _mmr_rerank(
        results: List[Dict[str, Any]], lambda_param: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        MMR（最大边际相关性）重排序

        平衡相关性和多样性。
        """
        if len(results) <= 1:
            return results

        tokenized = [MemoryStore._tokenize(r["chunk"]["text"]) for r in results]
        selected: List[int] = []
        remaining = list(range(len(results)))
        reranked: List[Dict[str, Any]] = []

        while remaining:
            best_idx = -1
            best_mmr = float("-inf")

            for idx in remaining:
                relevance = results[idx]["score"]
                max_sim = 0.0
                for sel_idx in selected:
                    sim = MemoryStore._jaccard_similarity(
                        tokenized[idx], tokenized[sel_idx]
                    )
                    if sim > max_sim:
                        max_sim = sim
                mmr = lambda_param * relevance - (1 - lambda_param) * max_sim
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = idx

            selected.append(best_idx)
            remaining.remove(best_idx)
            reranked.append(results[best_idx])

        return reranked

    def hybrid_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        混合搜索管道

        流程：关键词搜索 -> 向量搜索 -> 合并 -> 时间衰减 -> MMR 重排序 -> top_k

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        chunks = self._load_all_chunks()
        if not chunks:
            return []

        # 1. 关键词和向量搜索
        keyword_results = self._keyword_search(query, chunks, top_k=10)
        vector_results = self._vector_search(query, chunks, top_k=10)

        # 2. 合并结果
        merged = self._merge_hybrid_results(vector_results, keyword_results)

        # 3. 时间衰减
        decayed = self._temporal_decay(merged)

        # 4. MMR 重排序
        reranked = self._mmr_rerank(decayed)

        # 5. 格式化输出
        result = []
        for r in reranked[:top_k]:
            snippet = r["chunk"]["text"]
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."
            result.append({
                "path": r["chunk"]["path"],
                "score": round(r["score"], 4),
                "snippet": snippet
            })

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        获取记忆统计信息

        Returns:
            统计信息字典
        """
        evergreen = self.load_evergreen()
        daily_files = (
            list(self.memory_dir.glob("*.jsonl"))
            if self.memory_dir.is_dir()
            else []
        )

        total_entries = 0
        for f in daily_files:
            try:
                total_entries += sum(
                    1 for line in f.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
            except Exception:
                pass

        return {
            "evergreen_chars": len(evergreen),
            "daily_files": len(daily_files),
            "daily_entries": total_entries,
        }
