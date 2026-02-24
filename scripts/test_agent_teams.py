#!/usr/bin/env python3
"""
test_agent_teams.py - 手动测试 Agent Teams 升级功能

用法:
    python scripts/test_agent_teams.py

测试步骤:
1. MessageBus: send/read_inbox/broadcast
2. TeammateManager: spawn/list/config 持久化
3. Session 隔离验证
4. 懒加载验证（不触发 team 时不创建目录）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import shutil
import tempfile
from pathlib import Path

# ── 测试环境准备 ──────────────────────────────────────────────
TMP = Path(tempfile.mkdtemp(prefix="test_teams_"))
print(f"测试目录: {TMP}\n")

import backend.app.session as session_mod
import backend.app.tools.team_tools as tt

# 重定向到临时目录
session_mod.SESSIONS_DIR = TMP / "sessions"
session_mod._current_key = "test_001"
tt._bus = None
tt._team = None

PASS = "✅"
FAIL = "❌"
results = []

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append(condition)
    print(f"  {status} {name}" + (f": {detail}" if detail else ""))


# ── 1. MessageBus ─────────────────────────────────────────────
print("1. MessageBus")

bus = tt._get_bus()
r = bus.send("lead", "alice", "hello")
check("send 返回成功", r == "Sent message to alice", r)

msgs = bus.read_inbox("alice")
check("read_inbox 收到消息", len(msgs) == 1)
check("消息内容正确", msgs[0]["content"] == "hello" and msgs[0]["from"] == "lead")

drained = bus.read_inbox("alice")
check("read_inbox 已清空", drained == [])

check("read_inbox 不存在的收件人", bus.read_inbox("nobody") == [])

bus.send("lead", "alice", "b1")
bus.send("lead", "bob", "b2")
r = bus.broadcast("lead", "hi all", ["alice", "bob", "lead"])
check("broadcast 发送给2人", "2" in r, r)
check("broadcast 不发给自己", bus.read_inbox("lead") == [])

r_invalid = bus.send("lead", "alice", "x", msg_type="bad_type")
check("无效 msg_type 返回 Error", r_invalid.startswith("Error:"), r_invalid)

print()

# ── 2. TeammateManager ────────────────────────────────────────
print("2. TeammateManager")

team = tt._get_team()
team._loop = lambda name, role, prompt: None  # mock: 不实际调用 LLM

r = team.spawn("alice", "coder", "write tests")
check("spawn 返回成功", "alice" in r, r)

config_path = tt._get_team_dir() / "config.json"
config = json.loads(config_path.read_text())
members = {m["name"]: m for m in config["members"]}
check("config.json 已创建", "alice" in members)
check("role 正确", members["alice"]["role"] == "coder")

r2 = team.spawn("alice", "coder", "task2")
check("busy 时 spawn 返回 Error", r2.startswith("Error:"), r2)

team._find("alice")["status"] = "idle"
team._save()
r3 = team.spawn("alice", "reviewer", "task3")
check("idle 时可重新 spawn", "alice" in r3, r3)
check("role 已更新", team._find("alice")["role"] == "reviewer")

team.spawn("bob", "tester", "run tests")
listing = team.list_all()
check("list_all 包含 alice 和 bob", "alice" in listing and "bob" in listing, listing)

check("list_all 空时返回提示", "No teammates." in tt.TeammateManager(TMP / "empty_team").list_all())

print()

# ── 3. Session 隔离 ───────────────────────────────────────────
print("3. Session 隔离")

session_mod._current_key = "session_a"
tt._bus = None
tt._get_bus().send("lead", "alice", "from A")

session_mod._current_key = "session_b"
tt._bus = None
msgs_b = tt._get_bus().read_inbox("alice")
check("session_b 看不到 session_a 的消息", msgs_b == [])

session_mod._current_key = "session_a"
tt._bus = None
msgs_a = tt._get_bus().read_inbox("alice")
check("session_a 消息仍在", len(msgs_a) == 1 and msgs_a[0]["content"] == "from A")

old_bus = object()
old_team = object()
tt._bus = old_bus
tt._team = old_team
session_mod.set_session_key("session_c")
check("set_session_key 重置 _bus", tt._bus is None)
check("set_session_key 重置 _team", tt._team is None)

print()

# ── 4. 懒加载 ─────────────────────────────────────────────────
print("4. 懒加载")

session_mod._current_key = "lazy_test"
tt._bus = None
tt._team = None
team_dir = session_mod.SESSIONS_DIR / "lazy_test" / "team"
check("未使用时 team 目录不存在", not team_dir.exists())

tt._get_bus()
check("_get_bus() 后 team 目录创建", team_dir.exists())

tt._bus = None
inbox = tt.drain_lead_inbox() if tt._bus is not None else []
check("drain_lead_inbox 在 _bus=None 时跳过", inbox == [] and tt._bus is None)

print()

# ── 结果汇总 ──────────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"{'='*40}")
print(f"结果: {passed}/{total} 通过 {'✅ 全部通过' if passed == total else '❌ 有失败项'}")

# ── 5. LangChain @tool 函数 ───────────────────────────────────
print("5. LangChain @tool 函数")

# 重置到干净 session
session_mod._current_key = "tool_test"
tt._bus = None
tt._team = None

from backend.app.tools.team_tools import (
    spawn_teammate, list_teammates, send_message, read_inbox, broadcast
)

# mock _loop 避免 LLM 调用
tt._get_team()._loop = lambda name, role, prompt: None

r = spawn_teammate.invoke({"name": "alice", "role": "coder", "prompt": "write code"})
check("spawn_teammate tool 返回成功", "alice" in r, r)

r = list_teammates.invoke({})
check("list_teammates tool 包含 alice", "alice" in r, r)

r = send_message.invoke({"to": "alice", "content": "hello alice"})
check("send_message tool 发送成功", "alice" in r, r)

# alice 的 inbox 应有消息
msgs = tt._get_bus().read_inbox("alice")
check("send_message 消息写入 alice inbox", len(msgs) == 1 and msgs[0]["content"] == "hello alice")

# lead 发给自己测试 read_inbox
tt._get_bus().send("alice", "lead", "reply from alice")
r = read_inbox.invoke({})
data = json.loads(r)
check("read_inbox tool 返回 JSON", isinstance(data, list) and len(data) == 1)
check("read_inbox 消息内容正确", data[0]["content"] == "reply from alice")

# 再 spawn bob 测试 broadcast
tt._get_team()._loop = lambda name, role, prompt: None
spawn_teammate.invoke({"name": "bob", "role": "reviewer", "prompt": "review code"})
r = broadcast.invoke({"content": "meeting now"})
check("broadcast tool 发送给所有队友", "2" in r, r)
check("alice 收到 broadcast", len(tt._get_bus().read_inbox("alice")) == 1)
check("bob 收到 broadcast", len(tt._get_bus().read_inbox("bob")) == 1)

print()

# ── 结果汇总 ──────────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"{'='*40}")
print(f"结果: {passed}/{total} 通过 {'✅ 全部通过' if passed == total else '❌ 有失败项'}")

shutil.rmtree(TMP)
sys.exit(0 if passed == total else 1)
