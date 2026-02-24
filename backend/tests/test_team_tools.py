"""
test_team_tools.py - 测试 Agent Teams 升级内容

测试范围:
1. MessageBus: send/read_inbox/broadcast
2. TeammateManager: spawn/list/config 持久化
3. Session 隔离: 不同 session key 使用不同目录
4. 懒加载: 未使用 team 时不创建目录
"""

import json
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def isolate_session(monkeypatch, tmp_path):
    """每个测试使用独立的临时 session 目录"""
    import backend.app.session as session_mod
    import backend.app.tools.team_tools as tt

    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(session_mod, "_current_key", "test_session")
    tt._bus = None
    tt._team = None
    yield
    tt._bus = None
    tt._team = None


# ── 1. MessageBus ──────────────────────────────────────────────

def test_send_and_read_inbox():
    from backend.app.tools.team_tools import _get_bus
    bus = _get_bus()
    assert bus.send("lead", "alice", "hello") == "Sent message to alice"
    msgs = bus.read_inbox("alice")
    assert len(msgs) == 1
    assert msgs[0]["content"] == "hello"
    assert msgs[0]["from"] == "lead"
    assert msgs[0]["type"] == "message"


def test_read_inbox_drains():
    from backend.app.tools.team_tools import _get_bus
    bus = _get_bus()
    bus.send("lead", "alice", "msg1")
    bus.send("lead", "alice", "msg2")
    assert len(bus.read_inbox("alice")) == 2
    assert bus.read_inbox("alice") == []


def test_read_inbox_empty():
    from backend.app.tools.team_tools import _get_bus
    assert _get_bus().read_inbox("nonexistent") == []


def test_broadcast():
    from backend.app.tools.team_tools import _get_bus
    bus = _get_bus()
    result = bus.broadcast("lead", "hello all", ["alice", "bob", "lead"])
    assert "2" in result
    assert len(bus.read_inbox("alice")) == 1
    assert len(bus.read_inbox("bob")) == 1
    assert bus.read_inbox("lead") == []


def test_invalid_msg_type():
    from backend.app.tools.team_tools import _get_bus
    result = _get_bus().send("lead", "alice", "hi", msg_type="invalid_type")
    assert result.startswith("Error:")


# ── 2. TeammateManager ────────────────────────────────────────

def test_spawn_creates_config():
    from backend.app.tools.team_tools import _get_team, _get_team_dir
    team = _get_team()
    team._loop = lambda name, role, prompt: None
    team.spawn("alice", "coder", "write tests")
    config = json.loads((_get_team_dir() / "config.json").read_text())
    members = {m["name"]: m for m in config["members"]}
    assert members["alice"]["role"] == "coder"


def test_spawn_duplicate_idle():
    from backend.app.tools.team_tools import _get_team
    team = _get_team()
    team._loop = lambda name, role, prompt: None
    team.spawn("alice", "coder", "task1")
    team._find("alice")["status"] = "idle"
    team._save()
    result = team.spawn("alice", "reviewer", "task2")
    assert "alice" in result
    assert team._find("alice")["role"] == "reviewer"


def test_spawn_busy_returns_error():
    from backend.app.tools.team_tools import _get_team
    team = _get_team()
    team._loop = lambda name, role, prompt: None
    team.spawn("alice", "coder", "task1")
    result = team.spawn("alice", "coder", "task2")
    assert result.startswith("Error:")


def test_list_teammates_empty():
    from backend.app.tools.team_tools import _get_team
    assert _get_team().list_all() == "No teammates."


def test_list_teammates():
    from backend.app.tools.team_tools import _get_team
    team = _get_team()
    team._loop = lambda name, role, prompt: None
    team.spawn("alice", "coder", "task")
    team.spawn("bob", "reviewer", "task")
    listing = team.list_all()
    assert "alice" in listing and "coder" in listing
    assert "bob" in listing and "reviewer" in listing


# ── 3. Session 隔离 ───────────────────────────────────────────

def test_session_isolation(monkeypatch, tmp_path):
    import backend.app.session as session_mod
    import backend.app.tools.team_tools as tt

    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path / "sessions")

    monkeypatch.setattr(session_mod, "_current_key", "session_a")
    tt._bus = None
    tt._get_bus().send("lead", "alice", "from A")

    monkeypatch.setattr(session_mod, "_current_key", "session_b")
    tt._bus = None
    assert tt._get_bus().read_inbox("alice") == []

    monkeypatch.setattr(session_mod, "_current_key", "session_a")
    tt._bus = None
    msgs = tt._get_bus().read_inbox("alice")
    assert len(msgs) == 1 and msgs[0]["content"] == "from A"


def test_set_session_key_resets_singletons(monkeypatch):
    import backend.app.session as session_mod
    import backend.app.tools.team_tools as tt

    tt._bus = object()
    tt._team = object()
    session_mod.set_session_key("new_key")
    assert tt._bus is None
    assert tt._team is None


# ── 4. 懒加载 ─────────────────────────────────────────────────

def test_no_team_dir_without_usage(monkeypatch, tmp_path):
    import backend.app.session as session_mod
    import backend.app.tools.team_tools as tt

    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(session_mod, "_current_key", "lazy_test")
    tt._bus = None

    team_dir = tmp_path / "sessions" / "lazy_test" / "team"
    assert not team_dir.exists()
    tt._get_bus()
    assert team_dir.exists()


def test_drain_skips_when_bus_none():
    import backend.app.tools.team_tools as tt
    tt._bus = None
    inbox = tt.drain_lead_inbox() if tt._bus is not None else []
    assert inbox == []
    assert tt._bus is None
