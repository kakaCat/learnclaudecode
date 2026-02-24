import json
import threading
import uuid
from pathlib import Path

from backend.app.tools.base import WORKDIR
from backend.app.tools.file_tool import bash, read_file, write_file, edit_file


class TeammateManager:
    def __init__(self, team_dir: Path):
        self.dir = team_dir
        self.dir.mkdir(exist_ok=True)
        self.config_path = self.dir / "config.json"
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
        return f"Spawned '{name}' (role: {role})"

    def _loop(self, name: str, role: str, prompt: str):
        from backend.app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
        from backend.app.team.state import (get_bus, shutdown_requests, plan_requests, tracker_lock,
                                             scan_unclaimed_tasks, claim_task, POLL_INTERVAL, IDLE_TIMEOUT)
        from langchain_core.messages import HumanMessage
        from langchain_openai import ChatOpenAI
        from langchain.agents import create_agent
        from langchain_core.tools import tool
        import time

        bus = get_bus()
        team_name = self.config["team_name"]

        @tool
        def send_message(to: str, content: str, msg_type: str = "message") -> str:
            """Send message to a teammate."""
            return bus.send(name, to, content, msg_type)

        @tool
        def read_inbox_tool() -> str:
            """Read and drain your inbox."""
            return json.dumps(bus.read_inbox(name), indent=2)

        @tool
        def shutdown_response(request_id: str, approve: bool, reason: str = "") -> str:
            """Respond to a shutdown request. Set approve=True to shut down gracefully."""
            with tracker_lock:
                if request_id in shutdown_requests:
                    shutdown_requests[request_id]["status"] = "approved" if approve else "rejected"
            bus.send(name, "lead", reason, "shutdown_response",
                     {"request_id": request_id, "approve": approve})
            return f"Shutdown {'approved' if approve else 'rejected'}"

        @tool
        def plan_approval(plan: str) -> str:
            """Submit a plan for lead approval before starting major work."""
            req_id = str(uuid.uuid4())[:8]
            with tracker_lock:
                plan_requests[req_id] = {"from": name, "plan": plan, "status": "pending"}
            bus.send(name, "lead", plan, "plan_approval_response",
                     {"request_id": req_id, "plan": plan})
            return f"Plan submitted (request_id={req_id}). Waiting for lead approval."

        @tool
        def idle() -> str:
            """Signal that you have no more work. Enters idle polling phase."""
            return "Entering idle phase."

        @tool
        def claim_task_tool(task_id: int) -> str:
            """Claim a task from the task board by ID."""
            return claim_task(task_id, name)

        def _set_status(status: str):
            m = self._find(name)
            if m:
                m["status"] = status
                self._save()

        llm = ChatOpenAI(model=DEEPSEEK_MODEL, api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        teammate_tools = [bash, read_file, write_file, edit_file, send_message, read_inbox_tool,
                          shutdown_response, plan_approval, idle, claim_task_tool]
        sys_prompt = (
            f"You are '{name}', role: {role}, team: {team_name}, at {WORKDIR}. "
            f"Submit plans via plan_approval before major work. "
            f"Use idle tool when you have no more work. You will auto-claim new tasks."
        )
        agent = create_agent(llm, teammate_tools, system_prompt=sys_prompt)
        messages = [HumanMessage(content=prompt)]

        while True:
            # -- WORK PHASE --
            idle_requested = False
            for _ in range(50):
                for msg in bus.read_inbox(name):
                    msg_data = msg if isinstance(msg, dict) else json.loads(msg)
                    if msg_data.get("type") == "shutdown_request":
                        _set_status("shutdown")
                        return
                    messages.append(HumanMessage(content=json.dumps(msg_data)))
                try:
                    for step in agent.stream({"messages": messages}, stream_mode="updates"):
                        for node, state in step.items():
                            last = state["messages"][-1]
                            if node == "agent":
                                messages = state["messages"]
                                if not getattr(last, "tool_calls", None):
                                    break
                                for tc in last.tool_calls:
                                    if tc["name"] == "idle":
                                        idle_requested = True
                            elif node == "tools":
                                print(f"  [{name}] tool: {last.content[:120]}")
                        else:
                            continue
                        break
                except Exception:
                    _set_status("idle")
                    return
                if idle_requested or not getattr(messages[-1], "tool_calls", None):
                    break

            # -- IDLE PHASE --
            _set_status("idle")
            resume = False
            for _ in range(IDLE_TIMEOUT // max(POLL_INTERVAL, 1)):
                time.sleep(POLL_INTERVAL)
                inbox = bus.read_inbox(name)
                if inbox:
                    for msg in inbox:
                        msg_data = msg if isinstance(msg, dict) else json.loads(msg)
                        if msg_data.get("type") == "shutdown_request":
                            _set_status("shutdown")
                            return
                        messages.append(HumanMessage(content=json.dumps(msg_data)))
                    resume = True
                    break
                unclaimed = scan_unclaimed_tasks()
                if unclaimed:
                    task = unclaimed[0]
                    claim_task(task["id"], name)
                    task_prompt = (
                        f"<auto-claimed>Task #{task['id']}: {task['subject']}\n"
                        f"{task.get('description', '')}</auto-claimed>"
                    )
                    if len(messages) <= 3:
                        messages.insert(0, HumanMessage(
                            content=f"<identity>You are '{name}', role: {role}, team: {team_name}. Continue your work.</identity>"
                        ))
                    messages.append(HumanMessage(content=task_prompt))
                    resume = True
                    break

            if not resume:
                _set_status("shutdown")
                return
            _set_status("working")

    def list_all(self) -> str:
        if not self.config["members"]:
            return "No teammates."
        lines = [f"Team: {self.config['team_name']}"]
        for m in self.config["members"]:
            lines.append(f"  {m['name']} ({m['role']}): {m['status']}")
        return "\n".join(lines)

    def member_names(self) -> list:
        return [m["name"] for m in self.config["members"]]
