import time
from typing import Any, Callable

import pytest

from backend.app import auto_sync
from backend.app.models import SftpConfig, SyncStatus
from backend.app.sync_service import MissingCredentialsError, SyncInProgressError


class FakeTimer:
    def __init__(self, delay: float, func: Callable[[], Any], registry: list["FakeTimer"]):
        self.delay = delay
        self.func = func
        self.started = False
        self.cancelled = False
        registry.append(self)

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


def make_config(**overrides: Any) -> SftpConfig:
    base = dict(
        host="example.com",
        port=22,
        username="user",
        password="",
        remote_root="/remote",
        local_root="/local",
        sync_interval_minutes=5,
        auto_sync_enabled=True,
    )
    base.update(overrides)
    return SftpConfig(**base)


@pytest.fixture
def controller_fixture(monkeypatch: pytest.MonkeyPatch):
    events: list[tuple[str, dict[str, Any]]] = []
    next_times: list[float | None] = []
    timers: list[FakeTimer] = []

    def fake_log_event(event: str, **kwargs: Any) -> None:
        events.append((event, kwargs))

    def fake_set_next_sync_time(ts: float | None) -> None:
        next_times.append(ts)

    monkeypatch.setattr(auto_sync, "log_event", fake_log_event)
    monkeypatch.setattr(auto_sync.sync_service, "set_next_sync_time", fake_set_next_sync_time)
    monkeypatch.setattr(
        auto_sync.threading,
        "Timer",
        lambda delay, func: FakeTimer(delay, func, timers),
    )

    controller = auto_sync.AutoSyncController()
    return {
        "controller": controller,
        "events": events,
        "next_times": next_times,
        "timers": timers,
    }


def test_arm_timer_sets_next_run_and_sync_time(monkeypatch: pytest.MonkeyPatch, controller_fixture):
    controller: auto_sync.AutoSyncController = controller_fixture["controller"]
    next_times: list[float | None] = controller_fixture["next_times"]
    timers: list[FakeTimer] = controller_fixture["timers"]

    start = time.time()
    controller._arm_timer_locked(10)

    assert controller._next_run_time is not None
    assert abs(controller._next_run_time - (start + 10)) < 0.05
    assert len(timers) == 1
    assert timers[0].delay == 10
    assert timers[0].started is True
    assert next_times[-1] == controller._next_run_time


def test_ensure_start_on_restart_starts_from_idle_and_error(monkeypatch: pytest.MonkeyPatch, controller_fixture):
    controller: auto_sync.AutoSyncController = controller_fixture["controller"]
    events: list[tuple[str, dict[str, Any]]] = controller_fixture["events"]
    timers: list[FakeTimer] = controller_fixture["timers"]

    for state in ["idle", "error"]:
        controller.shutdown()
        timers.clear()
        events.clear()
        controller.update_config(make_config())

        started: list[SftpConfig] = []

        monkeypatch.setattr(auto_sync.sync_service, "status", lambda: SyncStatus(state=state))
        monkeypatch.setattr(auto_sync.sync_service, "start", lambda cfg: started.append(cfg))

        controller.ensure_start_on_restart()

        assert started and started[0].host == "example.com"
        assert len(timers) == 1
        assert timers[0].delay == 5 * 60
        assert any(event == "autosync.restart_trigger" for event, _ in events)


def test_ensure_start_on_restart_skips_when_active(monkeypatch: pytest.MonkeyPatch, controller_fixture):
    controller: auto_sync.AutoSyncController = controller_fixture["controller"]
    events: list[tuple[str, dict[str, Any]]] = controller_fixture["events"]
    timers: list[FakeTimer] = controller_fixture["timers"]

    controller.update_config(make_config())
    monkeypatch.setattr(auto_sync.sync_service, "status", lambda: SyncStatus(state="downloading"))
    start_called: list[bool] = []
    monkeypatch.setattr(auto_sync.sync_service, "start", lambda cfg: start_called.append(True))

    controller.ensure_start_on_restart()

    assert not start_called
    assert not timers
    assert not events


def test_ensure_start_on_restart_logs_in_progress(monkeypatch: pytest.MonkeyPatch, controller_fixture):
    controller: auto_sync.AutoSyncController = controller_fixture["controller"]
    events: list[tuple[str, dict[str, Any]]] = controller_fixture["events"]
    timers: list[FakeTimer] = controller_fixture["timers"]

    controller.update_config(make_config())
    monkeypatch.setattr(auto_sync.sync_service, "status", lambda: SyncStatus(state="idle"))
    monkeypatch.setattr(auto_sync.sync_service, "start", lambda cfg: (_ for _ in ()).throw(SyncInProgressError()))

    controller.ensure_start_on_restart()

    assert not timers
    assert [evt for evt, _ in events] == ["autosync.restart_trigger", "autosync.restart_skipped"]


def test_ensure_start_on_restart_logs_missing_credentials(monkeypatch: pytest.MonkeyPatch, controller_fixture):
    controller: auto_sync.AutoSyncController = controller_fixture["controller"]
    events: list[tuple[str, dict[str, Any]]] = controller_fixture["events"]
    timers: list[FakeTimer] = controller_fixture["timers"]

    controller.update_config(make_config())
    monkeypatch.setattr(auto_sync.sync_service, "status", lambda: SyncStatus(state="idle"))
    monkeypatch.setattr(
        auto_sync.sync_service,
        "start",
        lambda cfg: (_ for _ in ()).throw(MissingCredentialsError("missing password")),
    )

    controller.ensure_start_on_restart()

    assert not timers
    assert [evt for evt, _ in events] == ["autosync.restart_trigger", "autosync.restart_failed"]


def test_run_scheduled_sync_schedules_next_run(monkeypatch: pytest.MonkeyPatch, controller_fixture):
    controller: auto_sync.AutoSyncController = controller_fixture["controller"]
    events: list[tuple[str, dict[str, Any]]] = controller_fixture["events"]
    timers: list[FakeTimer] = controller_fixture["timers"]
    next_times: list[float | None] = controller_fixture["next_times"]

    config = make_config(sync_interval_minutes=5)
    monkeypatch.setattr(auto_sync.config_store, "export_unmasked_config", lambda: config)
    monkeypatch.setattr(auto_sync.sync_service, "start", lambda cfg: None)

    controller._run_scheduled_sync()

    assert controller._config is not None and controller._config.host == config.host
    assert len(timers) == 1
    assert timers[0].delay == 5 * 60
    assert next_times[-1] == controller._next_run_time
    assert any(event == "autosync.run_triggered" for event, _ in events)


def test_run_scheduled_sync_retries_when_in_progress(monkeypatch: pytest.MonkeyPatch, controller_fixture):
    controller: auto_sync.AutoSyncController = controller_fixture["controller"]
    events: list[tuple[str, dict[str, Any]]] = controller_fixture["events"]
    timers: list[FakeTimer] = controller_fixture["timers"]

    config = make_config()
    monkeypatch.setattr(auto_sync.config_store, "export_unmasked_config", lambda: config)
    monkeypatch.setattr(auto_sync.sync_service, "start", lambda cfg: (_ for _ in ()).throw(SyncInProgressError()))

    controller._run_scheduled_sync()

    assert len(timers) == 1
    assert timers[0].delay == 30
    event_names = [evt for evt, _ in events]
    assert event_names[0] == "autosync.run_triggered"
    assert "autosync.run_skipped" in event_names


def test_run_scheduled_sync_cancels_on_missing_credentials(monkeypatch: pytest.MonkeyPatch, controller_fixture):
    controller: auto_sync.AutoSyncController = controller_fixture["controller"]
    events: list[tuple[str, dict[str, Any]]] = controller_fixture["events"]
    next_times: list[float | None] = controller_fixture["next_times"]

    config = make_config()
    monkeypatch.setattr(auto_sync.config_store, "export_unmasked_config", lambda: config)
    monkeypatch.setattr(
        auto_sync.sync_service,
        "start",
        lambda cfg: (_ for _ in ()).throw(MissingCredentialsError("missing password")),
    )

    controller._run_scheduled_sync()

    assert controller._timer is None
    assert controller._next_run_time is None
    assert next_times[-1] is None
    event_names = [evt for evt, _ in events]
    assert event_names[0] == "autosync.run_triggered"
    assert "autosync.run_cancelled" in event_names


def test_run_scheduled_sync_retries_on_generic_error(monkeypatch: pytest.MonkeyPatch, controller_fixture):
    controller: auto_sync.AutoSyncController = controller_fixture["controller"]
    events: list[tuple[str, dict[str, Any]]] = controller_fixture["events"]
    timers: list[FakeTimer] = controller_fixture["timers"]

    config = make_config()
    monkeypatch.setattr(auto_sync.config_store, "export_unmasked_config", lambda: config)
    monkeypatch.setattr(auto_sync.sync_service, "start", lambda cfg: (_ for _ in ()).throw(RuntimeError("boom")))

    controller._run_scheduled_sync()

    assert len(timers) == 1
    assert timers[0].delay == 5 * 60
    event_names = [evt for evt, _ in events]
    assert event_names[0] == "autosync.run_triggered"
    assert "autosync.run_failed" in event_names
