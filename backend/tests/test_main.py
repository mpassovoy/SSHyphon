import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.models import ConfigResponse, JellyfinConfigResponse, SftpConfig, SyncStatus


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main.config_store, "AUTH_FILE", tmp_path / "auth.json")
    client = TestClient(main.app)
    main.config_store.save_auth_record({})
    setup_response = client.post("/api/auth/setup", json={"username": "tester", "password": "secret"})
    token = setup_response.json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _sample_config(password: str = "********") -> ConfigResponse:
    return ConfigResponse(
        host="example.com",
        port=22,
        username="demo",
        password=password,
        remote_root="/remote",
        local_root="/local",
        skip_folders=["cache", "tmp"],
        sync_interval_minutes=30,
        auto_sync_enabled=True,
        start_after=None,
        has_password=password != "",
        last_sync_time=1710000000.0,
    )


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_fastapi_version_matches_version_file():
    assert main.app.version == main.read_version()


def test_version_endpoint_returns_payload(monkeypatch, client):
    expected = {
        "version": "9.9.9",
        "latest_version": "9.9.9",
        "update_available": False,
        "checked_at": "2024-01-01T00:00:00Z",
        "repository": "example/repo",
    }

    monkeypatch.setattr(main, "get_version_payload", lambda: expected)

    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json()["version"] == expected["version"]
    assert response.json()["repository"] == expected["repository"]


def test_read_config_uses_config_store(monkeypatch, client):
    expected = _sample_config()
    monkeypatch.setattr(main.config_store, "get_config", lambda mask_secrets=True: expected)

    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["host"] == expected.host
    assert payload["has_password"] is True


def test_read_config_can_reveal_password(monkeypatch, client):
    called = {"mask": None}

    def fake_get_config(mask_secrets=True):
        called["mask"] = mask_secrets
        return _sample_config(password="hunter2")

    monkeypatch.setattr(main.config_store, "get_config", fake_get_config)

    response = client.get("/api/config?reveal=true")

    assert response.status_code == 200
    assert called["mask"] is False
    assert response.json()["password"] == "hunter2"


def test_update_config_updates_auto_sync(monkeypatch, client):
    saved_payload: SftpConfig | None = None
    updated_config = _sample_config(password="")

    def fake_save(config: SftpConfig):
        nonlocal saved_payload
        saved_payload = config
        return updated_config

    auto_sync_called = {"update": False}

    monkeypatch.setattr(main.config_store, "save_config", fake_save)
    monkeypatch.setattr(main.auto_sync_controller, "update_config", lambda cfg: auto_sync_called.__setitem__("update", True))

    response = client.put("/api/config", json=_sample_config().model_dump())

    assert response.status_code == 200
    assert saved_payload is not None
    assert auto_sync_called["update"] is True
    assert response.json()["local_root"] == updated_config.local_root


def test_status_endpoint_uses_sync_service(monkeypatch, client):
    status = SyncStatus(state="idle", message="Idle", progress=0)
    monkeypatch.setattr(main.sync_service, "status", lambda: status)

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["state"] == "idle"


def test_start_sync_schedules_next_run(monkeypatch, client):
    sample_status = SyncStatus(state="connecting", message="Connecting", progress=10)
    schedule_called = {"value": False}

    monkeypatch.setattr(main.config_store, "export_unmasked_config", lambda: _sample_config())
    monkeypatch.setattr(main.sync_service, "start", lambda cfg: sample_status)
    monkeypatch.setattr(main.auto_sync_controller, "schedule_next_run", lambda cfg: schedule_called.__setitem__("value", True))

    response = client.post("/api/sync/start")

    assert response.status_code == 200
    assert schedule_called["value"] is True
    assert response.json()["state"] == "connecting"


def test_start_sync_missing_credentials_returns_bad_request(monkeypatch, client):
    def fake_start(config: SftpConfig):
        raise main.MissingCredentialsError("Host, username, password, remote root, and local root are required.")

    schedule_called = {"value": False}

    monkeypatch.setattr(main.config_store, "export_unmasked_config", lambda: SftpConfig())
    monkeypatch.setattr(main.sync_service, "start", fake_start)
    monkeypatch.setattr(main.auto_sync_controller, "schedule_next_run", lambda cfg: schedule_called.__setitem__("value", True))

    response = client.post("/api/sync/start")

    assert response.status_code == 400
    assert "Host" in response.json()["detail"]
    assert schedule_called["value"] is False


def test_start_sync_conflict_returns_409(monkeypatch, client):
    def fake_start(config: SftpConfig):
        raise main.SyncInProgressError("Sync already running")

    monkeypatch.setattr(main.config_store, "export_unmasked_config", lambda: _sample_config())
    monkeypatch.setattr(main.sync_service, "start", fake_start)

    response = client.post("/api/sync/start")

    assert response.status_code == 409
    assert response.json()["detail"] == "Sync already running"


def test_stop_sync_cancels_auto_sync(monkeypatch, client):
    stop_status = SyncStatus(state="stopping", message="Stopping sync…")
    cancel_called = {"value": False}

    monkeypatch.setattr(main.auto_sync_controller, "cancel_schedule", lambda: cancel_called.__setitem__("value", True))
    monkeypatch.setattr(main.sync_service, "stop", lambda: stop_status)

    response = client.post("/api/sync/stop")

    assert response.status_code == 200
    assert cancel_called["value"] is True
    assert response.json()["state"] == "stopping"


def test_errors_endpoint_returns_tail(monkeypatch, client):
    errors = ["first", "second"]
    monkeypatch.setattr(main.config_store, "tail_errors", lambda limit=200: errors)

    response = client.get("/api/errors?limit=5")

    assert response.status_code == 200
    assert response.json() == {"errors": errors}


def test_errors_endpoint_uses_limit(monkeypatch, client):
    called = {"limit": None}

    def fake_tail(limit=200):
        called["limit"] = limit
        return ["only"]

    monkeypatch.setattr(main.config_store, "tail_errors", fake_tail)

    response = client.get("/api/errors?limit=3")

    assert response.status_code == 200
    assert called["limit"] == 3
    assert response.json()["errors"] == ["only"]


def test_read_jellyfin_config_can_reveal(monkeypatch, client):
    expected = JellyfinConfigResponse(server_url="http://jf", api_key="secret", has_api_key=True, tested=True)

    called = {"mask": None}

    def fake_get(mask_secrets=True):
        called["mask"] = mask_secrets
        return expected

    monkeypatch.setattr(main.config_store, "get_jellyfin_config", fake_get)

    response = client.get("/api/jellyfin/config?reveal=true")
    assert response.status_code == 200
    assert called["mask"] is False
    assert response.json()["api_key"] == "secret"


def test_read_jellyfin_config_failure_returns_500(monkeypatch, client):
    from fastapi import HTTPException

    monkeypatch.setattr(
        main.config_store,
        "get_jellyfin_config",
        lambda mask_secrets=True: (_ for _ in ()).throw(HTTPException(status_code=500, detail="boom")),
    )

    response = client.get("/api/jellyfin/config")
    assert response.status_code == 500
    assert "boom" in response.text


def test_clear_error_log_resets_file(tmp_path, monkeypatch, client):
    errors_file = tmp_path / "errors.log"
    errors_file.write_text("oops", encoding="utf-8")
    monkeypatch.setattr(main.config_store, "ERROR_LOG_FILE", errors_file)

    response = client.post("/api/errors/clear")

    assert response.status_code == 200
    assert errors_file.read_text(encoding="utf-8") == ""


def test_download_error_log_returns_file(tmp_path, monkeypatch, client):
    errors_file = tmp_path / "errors.log"
    errors_file.write_text("line one", encoding="utf-8")
    monkeypatch.setattr(main.config_store, "ERROR_LOG_FILE", errors_file)

    response = client.get("/api/errors/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.content == b"line one"


def test_download_error_log_creates_file_when_missing(tmp_path, monkeypatch, client):
    errors_file = tmp_path / "errors.log"
    monkeypatch.setattr(main.config_store, "ERROR_LOG_FILE", errors_file)

    response = client.get("/api/errors/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert errors_file.exists()
    assert response.content == b""


def test_activity_log_endpoints(monkeypatch, client):
    calls = {"limit": None, "cleared": False}

    def fake_read(limit=1000):
        calls["limit"] = limit
        return ["a", "b"]

    def fake_clear():
        calls["cleared"] = True

    monkeypatch.setattr(main, "read_activity_entries", fake_read)
    monkeypatch.setattr(main, "clear_activity_entries", fake_clear)

    list_response = client.get("/api/activity/log?limit=5")
    assert list_response.status_code == 200
    assert calls["limit"] == 5
    assert list_response.json() == {"entries": ["a", "b"]}

    clear_response = client.post("/api/activity/clear")
    assert clear_response.status_code == 200
    assert calls["cleared"] is True


def test_download_activity_log_serves_file(tmp_path, monkeypatch, client):
    log_file = tmp_path / "activity.log"
    log_file.write_text("entry", encoding="utf-8")
    monkeypatch.setattr(main, "ACTIVITY_LOG_FILE", log_file)

    response = client.get("/api/activity/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.content == b"entry"


def test_jellyfin_config_endpoints(monkeypatch, client):
    config_response = main.jellyfin_service.JellyfinConfig(server_url="http://demo", api_key="secret")
    monkeypatch.setattr(main.config_store, "get_jellyfin_config", lambda mask_secrets=True: config_response)

    saved_payload = {"server_url": "http://demo", "api_key": "secret"}
    monkeypatch.setattr(
        main.config_store,
        "save_jellyfin_config",
        lambda payload: payload if isinstance(payload, main.JellyfinConfig) else saved_payload,
    )

    read_response = client.get("/api/jellyfin/config?reveal=true")
    assert read_response.status_code == 200
    assert read_response.json()["server_url"] == "http://demo"

    update_response = client.put("/api/jellyfin/config", json=saved_payload)
    assert update_response.status_code == 200


def test_jellyfin_test_and_tasks(monkeypatch, client):
    called = {"test": False, "list": False, "run": False}

    monkeypatch.setattr(main.jellyfin_service, "test_connection", lambda payload=None: called.__setitem__("test", True))
    monkeypatch.setattr(main.jellyfin_service, "list_tasks", lambda: called.__setitem__("list", True) or [])
    monkeypatch.setattr(main.sync_service, "start_jellyfin_tasks", lambda: called.__setitem__("run", True) or [])

    assert client.post("/api/jellyfin/test").status_code == 200
    assert called["test"] is True

    assert client.get("/api/jellyfin/tasks").status_code == 200
    assert called["list"] is True

    assert client.post("/api/jellyfin/tasks/run").status_code == 200
    assert called["run"] is True


def test_jellyfin_error_handling(monkeypatch, client):
    monkeypatch.setattr(main.jellyfin_service, "test_connection", lambda payload=None: (_ for _ in ()).throw(Exception("bad")))
    resp_test = client.post("/api/jellyfin/test", json={"server_url": "x", "api_key": "y"})
    assert resp_test.status_code == 400

    monkeypatch.setattr(main.jellyfin_service, "list_tasks", lambda: (_ for _ in ()).throw(Exception("boom")))
    resp_list = client.get("/api/jellyfin/tasks")
    assert resp_list.status_code == 400

    monkeypatch.setattr(main.sync_service, "start_jellyfin_tasks", lambda: (_ for _ in ()).throw(RuntimeError("running")))
    resp_run_conflict = client.post("/api/jellyfin/tasks/run")
    assert resp_run_conflict.status_code == 409

    monkeypatch.setattr(main.sync_service, "start_jellyfin_tasks", lambda: (_ for _ in ()).throw(Exception("oops")))
    resp_run_error = client.post("/api/jellyfin/tasks/run")
    assert resp_run_error.status_code == 400
