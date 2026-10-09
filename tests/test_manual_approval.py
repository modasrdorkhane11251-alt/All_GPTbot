from datetime import datetime, timezone
from app import db
from app.config import S


def test_manual_approval_is_atomic_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "db_path", str(tmp_path / "test.sqlite3"))
    db.init_db()
    db.upsert(12345, "test-user")
    pid = db.create_payment(12345, "day")

    until = db.approve_payment(pid, 999)
    assert until is not None
    user = db.get_user(12345)
    assert datetime.fromisoformat(user["until"]) > datetime.now(timezone.utc)
    assert db.payment(pid)["status"] == "approved"

    # Re-running approval must not grant the same plan twice.
    assert db.approve_payment(pid, 999) is None
    assert db.get_user(12345)["until"] == until


def test_manual_approval_creates_missing_user(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "db_path", str(tmp_path / "test.sqlite3"))
    db.init_db()
    pid = db.create_payment(54321, "week")
    until = db.approve_payment(pid, 999)
    assert until is not None
    assert db.get_user(54321) is not None
    assert db.payment(pid)["status"] == "approved"
