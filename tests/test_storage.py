import asyncio
from datetime import datetime

import pytest

storage = pytest.importorskip("storage")
from storage import SessionStore, _jsonable  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def test_disabled_store_reads_return_empty(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = SessionStore()
    assert s.enabled is False
    assert _run(s.get_session("x")) is None
    assert _run(s.list_sessions()) == []
    assert _run(s.get_events("x")) == []
    assert _run(s.get_skill_scores("x")) == []
    assert _run(s.export_session("x")) == {}


def test_disabled_store_writes_are_noops(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = SessionStore()
    # None of these should raise when persistence is disabled.
    _run(s.upsert_session(session_id="x", round_type="dsa", resume_text="", resume_file_name="", weak_areas=[]))
    _run(s.add_event("x", "user", "hi"))
    _run(s.upsert_skill_scores("x", [{"skill": "a", "score": 3}]))
    _run(s.delete_session("x"))


def test_jsonable_converts_datetime():
    dt = datetime(2024, 1, 2, 3, 4, 5)
    r = _jsonable({"created_at": dt, "id": "s1"})
    assert r["created_at"] == dt.isoformat()
    assert r["id"] == "s1"


def test_jsonable_none_returns_empty():
    assert _jsonable(None) == {}
