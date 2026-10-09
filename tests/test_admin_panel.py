from fastapi.testclient import TestClient
from app import db
from app.config import S
from app.admin_panel import app


def test_panel_health_and_login_page(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "db_path", str(tmp_path / "panel.sqlite3"))
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "a-long-test-password")
    monkeypatch.setenv("ADMIN_PANEL_SECRET", "test-secret-that-is-long-enough")
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.get("/")
        assert response.status_code == 200
        assert "ورود به پنل مدیریت" in response.text


def test_panel_protects_mutations(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "db_path", str(tmp_path / "panel-protected.sqlite3"))
    with TestClient(app) as client:
        response = client.post("/user/quota", data={"uid": "123", "quota": "999"}, follow_redirects=False)
        assert response.status_code == 303
        assert db.get_user(123) is None
