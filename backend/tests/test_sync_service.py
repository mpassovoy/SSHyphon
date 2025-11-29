from pathlib import Path

import pytest

from backend.app import config_store, sync_service
from backend.app.models import JellyfinConfigResponse, SftpConfig, SyncStatus


class DummyThread:
    def __init__(self, alive: bool = True):
        self._alive = alive

    def is_alive(self) -> bool:
        return self._alive


class DummySFTPClient:
    def __init__(self):
        self.closed = False

    def listdir_attr(self, path):
        return []

    def open(self, *args, **kwargs):
        raise AssertionError("Unexpected SFTP file open")

    def close(self):
        self.closed = True


class DummySSHClient:
    def __init__(self):
        self.closed = False

    def set_missing_host_key_policy(self, *args, **kwargs):
        return None

    def connect(self, *args, **kwargs):
        return None

    def open_sftp(self):
        return DummySFTPClient()

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def patch_logging(monkeypatch):
    monkeypatch.setattr(sync_service, "log_event", lambda *a, **k: None)
    monkeypatch.setattr(sync_service, "log_activity_error", lambda *a, **k: None)
    monkeypatch.setattr(sync_service, "log_activity_warning", lambda *a, **k: None)
    monkeypatch.setattr(
        sync_service,
        "LOGGER",
        type(
            "L",
            (),
            {
                "debug": staticmethod(lambda *a, **k: None),
                "info": staticmethod(lambda *a, **k: None),
                "warning": staticmethod(lambda *a, **k: None),
                "exception": staticmethod(lambda *a, **k: None),
            },
        ),
    )


def build_config(**overrides):
    base = dict(host="host", port=22, username="user", password="pw", remote_root="/remote", local_root="/local")
    base.update(overrides)
    return SftpConfig(**base)


def test_start_requires_credentials(monkeypatch):
    service = sync_service.SyncService()
    config = SftpConfig()  # empty fields
    monkeypatch.setattr(config_store, "get_password_for_config", lambda cfg: "")
    with pytest.raises(sync_service.MissingCredentialsError):
        service.start(config)


def test_start_rejects_parallel_runs(monkeypatch):
    service = sync_service.SyncService()
    service._thread = DummyThread(alive=True)
    monkeypatch.setattr(config_store, "get_password_for_config", lambda cfg: "pw")
    with pytest.raises(sync_service.SyncInProgressError):
        service.start(build_config())


def test_run_success_sets_idle_and_records_sync(monkeypatch):
    service = sync_service.SyncService()
    recorded_time = 0

    def fake_record_last_sync(ts=None):
        nonlocal recorded_time
        recorded_time = ts or 123.45

    monkeypatch.setattr(sync_service, "SSHClient", DummySSHClient)
    monkeypatch.setattr(config_store, "get_password_for_config", lambda cfg: "pw")
    monkeypatch.setattr(config_store, "record_last_sync", fake_record_last_sync)
    monkeypatch.setattr(config_store, "get_last_sync_time", lambda: recorded_time)
    monkeypatch.setattr(Path, "mkdir", lambda self, parents=False, exist_ok=False: None, raising=False)
    monkeypatch.setattr(service, "_sync_directory", lambda **kwargs: service._bump_stats(files=1, bytes=10))
    monkeypatch.setattr(service, "_should_run_jellyfin_after_sync", lambda: False)

    service._run(build_config(), "pw")
    status = service.status()
    assert status.state == "idle"
    assert status.message == "Idle"
    assert recorded_time != 0


def test_run_failure_resets_state_and_skips_jellyfin(monkeypatch):
    service = sync_service.SyncService()
    jellyfin_started = False

    def fake_start_jellyfin():
        nonlocal jellyfin_started
        jellyfin_started = True

    monkeypatch.setattr(sync_service, "SSHClient", DummySSHClient)
    monkeypatch.setattr(config_store, "get_password_for_config", lambda cfg: "pw")
    monkeypatch.setattr(config_store, "record_last_sync", lambda ts=None: None)
    monkeypatch.setattr(config_store, "get_last_sync_time", lambda: None)
    monkeypatch.setattr(Path, "mkdir", lambda self, parents=False, exist_ok=False: None, raising=False)
    monkeypatch.setattr(service, "_sync_directory", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(service, "start_jellyfin_tasks", fake_start_jellyfin)

    service._run(build_config(), "pw")
    status = service.status()
    assert status.state == "error"
    assert status.last_error == "boom"
    assert jellyfin_started is False


def test_stop_handles_threads(monkeypatch):
    service = sync_service.SyncService()
    close_called = 0

    def mark_close():
        nonlocal close_called
        close_called += 1

    monkeypatch.setattr(service, "_close_active_connection", mark_close)

    # No threads
    result = service.stop()
    assert isinstance(result, SyncStatus)

    # Only SFTP thread
    service._stop_event.clear()
    service._jellyfin_stop_event.clear()
    service._thread = DummyThread(alive=True)
    result = service.stop()
    assert service._stop_event.is_set()
    assert result.state == "stopping"
    assert close_called == 1

    # Only Jellyfin thread
    service._stop_event.clear()
    service._jellyfin_stop_event.clear()
    service._thread = None
    service._jellyfin_thread = DummyThread(alive=True)
    result = service.stop()
    assert service._jellyfin_stop_event.is_set()
    assert result.state == "jellyfin"

    # Both threads
    service._stop_event.clear()
    service._jellyfin_stop_event.clear()
    service._thread = DummyThread(alive=True)
    service._jellyfin_thread = DummyThread(alive=True)
    result = service.stop()
    assert service._stop_event.is_set()
    assert service._jellyfin_stop_event.is_set()
    assert close_called == 2


def test_start_jellyfin_tasks_guards(monkeypatch):
    service = sync_service.SyncService()

    monkeypatch.setattr(config_store, "get_jellyfin_config", lambda: JellyfinConfigResponse(tested=False))
    with pytest.raises(RuntimeError):
        service.start_jellyfin_tasks()

    service._thread = DummyThread(alive=True)
    monkeypatch.setattr(config_store, "get_jellyfin_config", lambda: JellyfinConfigResponse(tested=True))
    with pytest.raises(RuntimeError):
        service.start_jellyfin_tasks()

    service._thread = None
    service._jellyfin_thread = DummyThread(alive=True)
    with pytest.raises(RuntimeError):
        service.start_jellyfin_tasks()
