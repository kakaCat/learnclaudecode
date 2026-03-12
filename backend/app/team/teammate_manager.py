import json
import logging
import threading
import uuid
from pathlib import Path

from backend.app.tools.base import WORKDIR
from backend.app.core import tracer

logger = logging.getLogger(__name__)


class TeammateManager:
    def __init__(self, team_dir: Path):
        from backend.app.session import get_team_config_path
        self.dir = team_dir
        self.dir.mkdir(exist_ok=True)
        self.config_path = get_team_config_path()
        self.config = json.loads(self.config_path.read_text()) if self.config_path.exists() else {"team_name": "default", "members": []}
        self.threads = {}

    def _find(self, name: str) -> dict:
        return next((m for m in self.config["members"] if m["name"] == name), None)

    def _save(self):
        self.config_path.write_text(json.dumps(self.config, indent=2, ensure_ascii=False))

    def spawn(self, name: str, role: str, prompt: str) -> str:
        member = self._find(name)
        if member:
            if member["status"] not in ("idle", "shutdown"):
                return f"Error: '{name}' is currently {member['status']}"
            member.update({"status": "working", "role": role})
        else:
            member = {"name": name, "role": role, "status": "working"}
            self.config["members"].append(member)
        self._save()
        t = threading.Thread(target=self._loop, args=(name, role, prompt), daemon=True)
        self.threads[name] = t
        t.start()
        logger.info("spawn_teammate: name=%s role=%s", name, role)
        tracer.emit("teammate.spawn", name=name, role=role)
        return f"Spawned '{name}' (role: {role})"

    def _loop(self, name: str, role: str, prompt: str):
        """
        Teammate 主循环（使用新的 TeamAgentService）

        Args:
            name: Teammate 名称
            role: Teammate 角色
            prompt: 初始任务提示
        """
        from backend.app.services.team_agent_service_v2 import TeamAgentService
        import asyncio

        # 获取 session_key
        session_key = "default"  # TODO: 从全局配置获取

        # 创建 TeamAgentService
        service = TeamAgentService(name, role, session_key, enable_lifecycle=False)

        # 运行异步循环
        try:
            asyncio.run(service.run_loop(prompt))
        except Exception as e:
            logger.error(f"[{name}] Loop failed: {e}", exc_info=True)
            self._set_member_status(name, "error")

    def _set_member_status(self, name: str, status: str):
        """更新成员状态"""
        for member in self.config["members"]:
            if member["name"] == name:
                member["status"] = status
                break
        self._save()

    def list_all(self) -> str:
        if not self.config["members"]:
            return "No teammates."
        lines = [f"Team: {self.config['team_name']}"]
        for m in self.config["members"]:
            lines.append(f"  {m['name']} ({m['role']}): {m['status']}")
        return "\n".join(lines)

    def member_names(self) -> list:
        return [m["name"] for m in self.config["members"]]
