import requests
import pytest

from backend.app import jellyfin_service
from backend.app.models import JellyfinConfig, JellyfinConfigResponse, JellyfinSelectedTask


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


class FakeSession:
    def __init__(
        self,
        *,
        task_map=None,
        status_queue=None,
        post_status=204,
        delete_status=204,
        get_side_effects=None,
    ):
        self.task_map = task_map or []
        self.status_queue = status_queue or []
        self.post_status = post_status
        self.delete_status = delete_status
        self.get_side_effects = get_side_effects or []
        self.delete_calls = []
        self.post_calls = []

    def get(self, path, timeout=20):
        if self.get_side_effects:
            side_effect = self.get_side_effects.pop(0)
            if isinstance(side_effect, Exception):
                raise side_effect
            return side_effect
        if path == "/ScheduledTasks":
            return FakeResponse(json_data=self.task_map)
        if path.startswith("/ScheduledTasks/"):
            if not self.status_queue:
                raise RuntimeError("Status queue exhausted")
            next_status = self.status_queue.pop(0)
            if isinstance(next_status, Exception):
                raise next_status
            status_code = next_status.pop("status_code", 200) if isinstance(next_status, dict) else 200
            return FakeResponse(status_code=status_code, json_data=next_status)
        raise RuntimeError(f"Unexpected GET path: {path}")

    def post(self, path, timeout=20):
        self.post_calls.append(path)
        return FakeResponse(status_code=self.post_status, text="Started" if self.post_status == 204 else "Error")

    def delete(self, path, timeout=20):
        self.delete_calls.append(path)
        return FakeResponse(status_code=self.delete_status, text="Cancelled")


class FakeEvent:
    def __init__(self):
        self._flag = False

    def is_set(self):
        return self._flag

    def set(self):
        self._flag = True


def make_config(selected_tasks, include_hidden=True):
    return JellyfinConfigResponse(
        server_url="http://example", api_key="token", selected_tasks=selected_tasks, include_hidden_tasks=include_hidden, tested=True, has_api_key=True
    )


def test_fetch_task_map_respects_hidden_tasks():
    session = FakeSession(
        task_map=[
            {"Id": "1", "Key": "visible", "Name": "Visible", "IsHidden": False},
            {"Id": "2", "Key": "hidden", "Name": "Hidden", "IsHidden": True},
        ]
    )

    mapping = jellyfin_service._fetch_task_map(session, include_hidden=False, return_raw=True)
    assert "visible" in mapping
    assert "hidden" not in mapping

    mapping_with_hidden = jellyfin_service._fetch_task_map(session, include_hidden=True, return_raw=True)
    assert set(mapping_with_hidden.keys()) == {"visible", "hidden"}


def test_start_task_success_and_failure():
    success_session = FakeSession(post_status=204)
    jellyfin_service._start_task(success_session, "task123", "Task")

    failure_session = FakeSession(post_status=500)
    with pytest.raises(RuntimeError):
        jellyfin_service._start_task(failure_session, "task123", "Task")


def test_run_selected_tasks_completes(monkeypatch):
    tasks = [JellyfinSelectedTask(key="task-key", name="Library Refresh", order=1)]
    cfg = make_config(tasks)
    session = FakeSession(
        task_map=[{"Id": "abc", "Key": "task-key", "Name": "Library Refresh"}],
        status_queue=[{"CurrentProgressPercentage": 10, "State": "Running"}, {"CurrentProgressPercentage": 100, "State": "Completed"}],
    )

    progress = []

    monkeypatch.setattr(jellyfin_service, "get_jellyfin_config", lambda mask_secrets=False: cfg)
    monkeypatch.setattr(jellyfin_service, "_build_session_from_config", lambda cfg, override_api_key=None: session)

    jellyfin_service.run_selected_tasks(FakeEvent(), lambda name, prog, state, index, total: progress.append((prog, state)), poll_interval=0)

    assert progress[-1] == (100, "Completed")
    assert session.post_calls == ["/ScheduledTasks/Running/abc"]


def test_run_selected_tasks_handles_completed_with_errors(monkeypatch):
    tasks = [JellyfinSelectedTask(key="task-key", name="Metadata", order=1)]
    cfg = make_config(tasks)
    session = FakeSession(
        task_map=[{"Id": "abc", "Key": "task-key", "Name": "Metadata"}],
        status_queue=[{"CurrentProgressPercentage": 50, "State": "CompletedWithErrors"}],
    )

    monkeypatch.setattr(jellyfin_service, "get_jellyfin_config", lambda mask_secrets=False: cfg)
    monkeypatch.setattr(jellyfin_service, "_build_session_from_config", lambda cfg, override_api_key=None: session)

    jellyfin_service.run_selected_tasks(FakeEvent(), lambda *args, **kwargs: None, poll_interval=0)
    assert session.post_calls == ["/ScheduledTasks/Running/abc"]


def test_run_selected_tasks_cancellation_requests_delete(monkeypatch):
    tasks = [JellyfinSelectedTask(key="task-key", name="Maintenance", order=1)]
    cfg = make_config(tasks)
    session = FakeSession(
        task_map=[{"Id": "abc", "Key": "task-key", "Name": "Maintenance"}],
        status_queue=[{"CurrentProgressPercentage": 0, "State": "Running"}],
    )

    stop_event = FakeEvent()

    def progress_callback(name, prog, state, index, total):
        if state == "Starting":
            stop_event.set()

    monkeypatch.setattr(jellyfin_service, "get_jellyfin_config", lambda mask_secrets=False: cfg)
    monkeypatch.setattr(jellyfin_service, "_build_session_from_config", lambda cfg, override_api_key=None: session)

    with pytest.raises(RuntimeError, match="cancelled"):
        jellyfin_service.run_selected_tasks(stop_event, progress_callback, poll_interval=0)

    assert session.delete_calls == ["/ScheduledTasks/Running/abc"]


def test_run_selected_tasks_consecutive_poll_failures(monkeypatch):
    tasks = [JellyfinSelectedTask(key="task-key", name="Cleanup", order=1)]
    cfg = make_config(tasks)
    session = FakeSession(task_map=[{"Id": "abc", "Key": "task-key", "Name": "Cleanup"}])

    monkeypatch.setattr(jellyfin_service, "get_jellyfin_config", lambda mask_secrets=False: cfg)
    monkeypatch.setattr(jellyfin_service, "_build_session_from_config", lambda cfg, override_api_key=None: session)

    failure = requests.RequestException("boom")
    monkeypatch.setattr(jellyfin_service, "_get_task_status", lambda *args, **kwargs: (_ for _ in ()).throw(failure))

    with pytest.raises(RuntimeError, match="Failed to poll 'Cleanup'"):
        jellyfin_service.run_selected_tasks(FakeEvent(), lambda *args, **kwargs: None, poll_interval=0)


def test_run_selected_tasks_missing_task(monkeypatch):
    tasks = [JellyfinSelectedTask(key="task-key", name="Missing Task", order=1)]
    cfg = make_config(tasks)

    monkeypatch.setattr(jellyfin_service, "get_jellyfin_config", lambda mask_secrets=False: cfg)
    monkeypatch.setattr(jellyfin_service, "_build_session_from_config", lambda cfg, override_api_key=None: FakeSession())
    monkeypatch.setattr(jellyfin_service, "_fetch_task_map", lambda *args, **kwargs: {})

    with pytest.raises(RuntimeError, match="was not found"):
        jellyfin_service.run_selected_tasks(FakeEvent(), lambda *args, **kwargs: None, poll_interval=0)


def test_get_task_status_returns_completed_on_404():
    session = FakeSession(status_queue=[{"status_code": 404}])
    status = jellyfin_service._get_task_status(session, "abc")
    assert status == {"CurrentProgressPercentage": 100, "State": "Completed"}


def test_get_ordered_selected_tasks_filters_and_sorts():
    tasks = [
        JellyfinSelectedTask(key="b", name="B", enabled=True, order=2),
        JellyfinSelectedTask(key="a", name="A", enabled=False, order=1),
        JellyfinSelectedTask(key="c", name="C", enabled=True, order=1),
    ]
    cfg = JellyfinConfig(server_url="http://example", api_key="token", selected_tasks=tasks)

    ordered = jellyfin_service._get_ordered_selected_tasks(cfg)
    assert [task.key for task in ordered] == ["c", "b"]
