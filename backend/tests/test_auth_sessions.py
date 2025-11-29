import time

import pytest

from fastapi.testclient import TestClient

from backend.app import auth, main
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials


@pytest.fixture(autouse=True)
def reset_sessions():
    auth._sessions.clear()
    yield
    auth._sessions.clear()


def _build_client(tmp_path, monkeypatch):
    monkeypatch.setattr(main.config_store, "AUTH_FILE", tmp_path / "auth.json")
    client = TestClient(main.app)
    main.config_store.save_auth_record({})
    return client


def test_login_honors_remember_me(monkeypatch, tmp_path):
    client = _build_client(tmp_path, monkeypatch)

    setup_response = client.post(
        "/api/auth/setup",
        json={"username": "tester", "password": "secret", "remember_me": False},
    )
    assert setup_response.status_code == 200

    short_session = client.post(
        "/api/auth/login", json={"username": "tester", "password": "secret"}
    )
    remembered_session = client.post(
        "/api/auth/login",
        json={"username": "tester", "password": "secret", "remember_me": True},
    )

    assert short_session.status_code == 200
    assert remembered_session.status_code == 200

    short_expires_at = short_session.json()["expires_at"]
    remembered_expires_at = remembered_session.json()["expires_at"]

    now = time.time()
    assert auth.SESSION_TTL_SECONDS - 10 <= short_expires_at - now <= auth.SESSION_TTL_SECONDS + 10
    assert auth.REMEMBER_ME_TTL_SECONDS - 10 <= remembered_expires_at - now <= auth.REMEMBER_ME_TTL_SECONDS + 10


def test_login_logs_success(monkeypatch, tmp_path):
    client = _build_client(tmp_path, monkeypatch)
    events: list[tuple[str, dict]] = []
    errors: list[tuple[str, dict]] = []

    monkeypatch.setattr(auth, "log_event", lambda action, **details: events.append((action, details)))
    monkeypatch.setattr(auth, "log_error", lambda action, **details: errors.append((action, details)))

    setup_response = client.post(
        "/api/auth/setup",
        json={"username": "tester", "password": "secret", "remember_me": False},
    )
    assert setup_response.status_code == 200

    login_response = client.post(
        "/api/auth/login", json={"username": "tester", "password": "secret"}
    )

    assert login_response.status_code == 200
    assert events == [("auth.login", {"username": "tester", "remember_me": False})]
    assert errors == []


def test_login_logs_failure(monkeypatch, tmp_path):
    client = _build_client(tmp_path, monkeypatch)
    events: list[tuple[str, dict]] = []
    errors: list[tuple[str, dict]] = []

    monkeypatch.setattr(auth, "log_event", lambda action, **details: events.append((action, details)))
    monkeypatch.setattr(auth, "log_error", lambda action, **details: errors.append((action, details)))

    setup_response = client.post(
        "/api/auth/setup",
        json={"username": "tester", "password": "secret", "remember_me": False},
    )
    assert setup_response.status_code == 200

    login_response = client.post(
        "/api/auth/login", json={"username": "tester", "password": "wrong"}
    )

    assert login_response.status_code == 401
    assert events == []
    assert errors == [("auth.login_failed", {"username": "tester", "reason": "invalid_password"})]


def test_expired_tokens_are_evicted(monkeypatch, tmp_path):
    client = _build_client(tmp_path, monkeypatch)

    # Seed an expired session and a valid one
    past = time.time() - 10
    future = time.time() + 100
    expired = auth.SessionInfo(username="old", token="expired", expires_at=past)
    valid = auth.SessionInfo(username="new", token="valid", expires_at=future)
    auth._sessions.update({expired.token: expired, valid.token: valid})

    status = client.get("/api/auth/status", headers={"Authorization": "Bearer expired"})
    assert status.status_code == 200
    payload = status.json()
    assert payload["authenticated"] is False
    assert expired.token not in auth._sessions
    assert valid.token in auth._sessions


def test_logout_clears_session(monkeypatch, tmp_path):
    client = _build_client(tmp_path, monkeypatch)
    auth._sessions["dead"] = auth.SessionInfo(username="tester", token="dead", expires_at=time.time() + 100)

    response = client.post("/api/auth/logout", headers={"Authorization": "Bearer dead"})

    assert response.status_code == 200
    assert "dead" not in auth._sessions


def test_optional_token_allows_missing_header():
    assert auth.optional_token(None) is None
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="abc")
    assert auth.optional_token(creds) == "abc"
