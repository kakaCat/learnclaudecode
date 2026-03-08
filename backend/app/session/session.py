"""
store.py - 统一的 Session 存储管理

合并了 session.py 和 analysis/session_store.py 的功能
提供完整的会话管理能力：
1. 会话创建和切换
2. 细粒度保存（save_turn, save_tool_result, save_compaction）
3. 元数据索引管理
4. 历史记录加载
5. Bootstrap 文件加载（参考 s06_intelligence.py）
6. 记忆管理（参考 s06_intelligence.py）
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import SESSIONS_DIR, SESSIONS_INDEX
from .bootstrap import BootstrapLoader
from .memory_store import MemoryStore


class SessionStore:
    """统一的会话存储管理器"""

    def __init__(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, dict] = self._load_index()
        self._current_key: str | None = None
        self._bootstrap_loader: Optional[BootstrapLoader] = None
        self._memory_store: Optional[MemoryStore] = None

    def _load_index(self) -> dict[str, dict]:
        """加载 sessions.json 索引"""
        if not SESSIONS_INDEX.exists():
            return {}
        try:
            return json.loads(SESSIONS_INDEX.read_text())
        except Exception:
            return {}

    def _save_index(self) -> None:
        """保存 sessions.json 索引"""
        SESSIONS_INDEX.write_text(json.dumps(self._index, indent=2, ensure_ascii=False))

    def create_session(self, key: str | None = None) -> str:
        """创建新会话并返回 key"""
        if key is None:
            key = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        session_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()

        metadata = {
            "session_key": key,
            "session_id": session_id,
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
            "compaction_count": 0,
            "skills_dir": None,  # 可选的 skills 目录路径
        }

        self._index[key] = metadata
        self._save_index()

        # 创建会话目录结构
        session_dir = SESSIONS_DIR / key
        session_dir.mkdir(parents=True, exist_ok=True)

        # 创建标准子目录
        (session_dir / "workspace").mkdir(exist_ok=True)
        (session_dir / "tasks").mkdir(exist_ok=True)
        (session_dir / "team").mkdir(exist_ok=True)
        (session_dir / "team" / "inbox").mkdir(exist_ok=True)
        (session_dir / "board").mkdir(exist_ok=True)

        # 写入主 transcript 元数据
        main_transcript = session_dir / "main.jsonl"
        with open(main_transcript, "w") as f:
            f.write(json.dumps({
                "type": "session",
                "id": session_id,
                "key": key,
                "created": now,
            }, ensure_ascii=False) + "\n")

        return key

    def get_current_key(self) -> str | None:
        """获取当前会话 key"""
        return self._current_key

    def set_current_key(self, key: str) -> None:
        """设置当前会话 key"""
        if key not in self._index:
            self.create_session(key)
        self._current_key = key

        # 初始化 Bootstrap 加载器（使用全局 .bootstrap 目录）
        self._bootstrap_loader = BootstrapLoader()

        # 初始化记忆存储（使用 session workspace）
        workspace_dir = self.get_workspace_dir(key)
        self._memory_store = MemoryStore(workspace_dir)

        # 重置 team 单例（如果存在）
        try:
            import backend.app.team.state as _ts
            _ts._bus = None
            _ts._team = None
        except ImportError:
            pass

    def get_session_dir(self, key: str | None = None) -> Path:
        """获取会话目录"""
        k = key or self._current_key or "default"
        d = SESSIONS_DIR / k
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_workspace_dir(self, key: str | None = None) -> Path:
        """获取 workspace 目录"""
        d = self.get_session_dir(key) / "workspace"
        d.mkdir(exist_ok=True)
        return d

    def get_tasks_dir(self, key: str | None = None) -> Path:
        """获取 tasks 目录"""
        d = self.get_session_dir(key) / "tasks"
        d.mkdir(exist_ok=True)
        return d

    def get_team_dir(self, key: str | None = None) -> Path:
        """获取 team 目录"""
        d = self.get_session_dir(key) / "team"
        d.mkdir(exist_ok=True)
        (d / "inbox").mkdir(exist_ok=True)
        return d

    def get_board_dir(self, key: str | None = None) -> Path:
        """获取 board 目录"""
        d = self.get_session_dir(key) / "board"
        d.mkdir(exist_ok=True)
        return d

    # ========================================================================
    # 文件路径辅助函数
    # ========================================================================

    def get_task_file_path(self, task_id: int, slug: str = "", key: str | None = None) -> Path:
        """获取 task 文件路径

        Args:
            task_id: 任务 ID
            slug: 任务标题的 slug（可选）
            key: 会话 key（可选）

        Returns:
            Path: tasks/task_{id}_{slug}.json
        """
        filename = f"task_{task_id}_{slug}.json" if slug else f"task_{task_id}.json"
        return self.get_tasks_dir(key) / filename

    def get_board_task_path(self, task_id: int, key: str | None = None) -> Path:
        """获取 board task 文件路径

        Args:
            task_id: 任务 ID
            key: 会话 key（可选）

        Returns:
            Path: board/task_{id}.json
        """
        return self.get_board_dir(key) / f"task_{task_id}.json"

    def get_team_config_path(self, key: str | None = None) -> Path:
        """获取 team 配置文件路径

        Args:
            key: 会话 key（可选）

        Returns:
            Path: team/config.json
        """
        return self.get_team_dir(key) / "config.json"

    def get_inbox_path(self, agent_name: str, key: str | None = None) -> Path:
        """获取 inbox 消息文件路径

        Args:
            agent_name: Agent 名称
            key: 会话 key（可选）

        Returns:
            Path: team/inbox/{agent_name}.jsonl
        """
        return self.get_team_dir(key) / "inbox" / f"{agent_name}.jsonl"

    def get_agent_transcript_path(self, agent_name: str, key: str | None = None) -> Path:
        """获取 agent transcript 文件路径

        Args:
            agent_name: Agent 名称
            key: 会话 key（可选）

        Returns:
            Path: {agent_name}.jsonl
        """
        return self.get_session_dir(key) / f"{agent_name}.jsonl"

    def append_transcript(self, agent_name: str, entry: dict, key: str | None = None) -> None:
        """追加条目到 agent 的 JSONL transcript"""
        k = key or self._current_key
        if not k:
            return

        path = self.get_session_dir(k) / f"{agent_name}.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def save_turn(self, agent_name: str, user_msg: str, ai_msg: str,
                  tool_calls: list[dict] | None = None, key: str | None = None) -> None:
        """保存一轮对话"""
        k = key or self._current_key
        if not k or k not in self._index:
            return

        now = datetime.now(timezone.utc).isoformat()

        # 保存用户消息
        self.append_transcript(agent_name, {
            "type": "user",
            "content": user_msg,
            "ts": now,
        }, k)

        # 保存 AI 消息
        self.append_transcript(agent_name, {
            "type": "assistant",
            "content": ai_msg,
            "tool_calls": tool_calls or [],
            "ts": now,
        }, k)

        # 更新元数据
        meta = self._index[k]
        meta["updated_at"] = now
        meta["message_count"] = meta.get("message_count", 0) + 1
        self._save_index()

    def save_tool_result(self, agent_name: str, tool_name: str,
                        tool_call_id: str, result: str, key: str | None = None) -> None:
        """保存工具执行结果"""
        k = key or self._current_key
        if not k:
            return

        self.append_transcript(agent_name, {
            "type": "tool_result",
            "tool": tool_name,
            "tool_call_id": tool_call_id,
            "result": result[:1000],  # 截断长结果
            "ts": datetime.now(timezone.utc).isoformat(),
        }, k)

    def save_compaction(self, agent_name: str, kind: str,
                       before_count: int, after_count: int, key: str | None = None) -> None:
        """记录压缩事件"""
        k = key or self._current_key
        if not k:
            return

        self.append_transcript(agent_name, {
            "type": "compaction",
            "kind": kind,  # micro/auto/manual
            "before_count": before_count,
            "after_count": after_count,
            "ts": datetime.now(timezone.utc).isoformat(),
        }, k)

        # 更新元数据
        if k in self._index:
            meta = self._index[k]
            meta["compaction_count"] = meta.get("compaction_count", 0) + 1
            self._save_index()

    def load_history(self, agent_name: str, key: str | None = None) -> list:
        """从 JSONL transcript 加载历史记录"""
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

        k = key or self._current_key
        if not k:
            return []

        path = self.get_session_dir(k) / f"{agent_name}.jsonl"
        if not path.exists():
            return []

        history = []
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                entry_type = entry.get("type")

                if entry_type == "session":
                    continue  # 跳过元数据行
                elif entry_type == "user":
                    history.append(HumanMessage(content=entry.get("content", "")))
                elif entry_type == "assistant":
                    history.append(AIMessage(content=entry.get("content", "")))
                elif entry_type == "tool_result":
                    history.append(ToolMessage(
                        content=entry.get("result", ""),
                        tool_call_id=entry.get("tool_call_id", "")
                    ))
                elif entry_type == "compaction":
                    # 压缩事件可以记录但不加入历史
                    pass
            except Exception:
                continue

        return history

    def save_full_history(self, agent_name: str, history: list, key: str | None = None) -> None:
        """保存完整历史（向后兼容旧的 save_session 方法）"""
        k = key or self._current_key
        if not k or not history:
            return

        # 覆盖写入完整历史
        path = self.get_session_dir(k) / f"{agent_name}.jsonl"
        with open(path, "w") as f:
            # 写入会话元数据
            if k in self._index:
                meta = self._index[k]
                f.write(json.dumps({
                    "type": "session",
                    "id": meta.get("session_id", ""),
                    "key": k,
                    "created": meta.get("created_at", ""),
                }, ensure_ascii=False) + "\n")

            # 写入消息
            for msg in history:
                f.write(json.dumps(msg.model_dump(), ensure_ascii=False) + "\n")

    def list_sessions(self) -> list[dict]:
        """列出所有会话，按更新时间排序"""
        sessions = list(self._index.values())
        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return sessions

    def delete_session(self, key: str) -> bool:
        """删除会话"""
        if key not in self._index:
            return False

        self._index.pop(key)
        self._save_index()

        # 删除目录
        import shutil
        session_dir = SESSIONS_DIR / key
        if session_dir.exists():
            shutil.rmtree(session_dir)

        return True

    def get_skills_dir(self, key: str | None = None) -> Path | None:
        """获取会话的 skills 目录路径"""
        k = key or self._current_key
        if not k or k not in self._index:
            return None

        skills_path = self._index[k].get("skills_dir")
        if skills_path:
            return Path(skills_path)
        return None

    def set_skills_dir(self, skills_dir: str | Path, key: str | None = None) -> None:
        """设置会话的 skills 目录路径"""
        k = key or self._current_key
        if not k or k not in self._index:
            raise ValueError(f"Session {k} not found")

        self._index[k]["skills_dir"] = str(skills_dir)
        self._index[k]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_index()

    # ========== Bootstrap 文件加载 ==========

    def get_bootstrap_loader(self) -> Optional[BootstrapLoader]:
        """获取当前会话的 Bootstrap 加载器"""
        return self._bootstrap_loader

    def load_bootstrap(self, mode: str = "full") -> Dict[str, str]:
        """
        加载 Bootstrap 文件

        Args:
            mode: 加载模式（full/minimal/none）

        Returns:
            文件名 -> 内容的字典
        """
        if not self._bootstrap_loader:
            return {}
        return self._bootstrap_loader.load_all(mode)

    def load_soul(self) -> str:
        """
        加载 SOUL.md 文件

        Returns:
            SOUL.md 内容
        """
        if not self._bootstrap_loader:
            return ""
        from .bootstrap import load_soul
        return load_soul()

    # ========== 记忆管理 ==========

    def get_memory_store(self) -> Optional[MemoryStore]:
        """获取当前会话的记忆存储"""
        return self._memory_store

    def write_memory(self, content: str, category: str = "general") -> str:
        """
        写入记忆

        Args:
            content: 记忆内容
            category: 分类

        Returns:
            操作结果消息
        """
        if not self._memory_store:
            return "Error: No active session"
        return self._memory_store.write_memory(content, category)

    def search_memory(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索记忆（简单 TF-IDF）

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        if not self._memory_store:
            return []
        return self._memory_store.search_memory(query, top_k)

    def hybrid_search_memory(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        混合搜索记忆（关键词 + 向量 + 时间衰减 + MMR）

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        if not self._memory_store:
            return []
        return self._memory_store.hybrid_search(query, top_k)

    def get_memory_stats(self) -> Dict[str, Any]:
        """
        获取记忆统计信息

        Returns:
            统计信息字典
        """
        if not self._memory_store:
            return {"evergreen_chars": 0, "daily_files": 0, "daily_entries": 0}
        return self._memory_store.get_stats()
