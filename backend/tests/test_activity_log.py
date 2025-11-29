import importlib

import pytest

from backend.app import activity_log


@pytest.fixture(autouse=True)
def reload_log(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNC_MONITOR_DATA_DIR", str(tmp_path))
    importlib.reload(activity_log)
    yield
    importlib.reload(activity_log)


def test_serialize_falls_back_on_failure():
    class Bad:
        def __str__(self):
            raise ValueError("boom")

        def __repr__(self):
            return "<bad>"

    payload = {"action": "test", "bad": Bad()}
    result = activity_log._serialize(payload)
    assert result == "{'action': 'test', 'bad': <bad>}"


def test_read_entries_handles_missing_and_errors(monkeypatch):
    assert activity_log.read_entries() == []

    def blow_up(self, *args, **kwargs):
        raise OSError("cannot read")

    monkeypatch.setattr(activity_log.Path, "read_text", blow_up, raising=False)
    assert activity_log.read_entries() == []


def test_clear_entries_resets_file(tmp_path):
    activity_log.ACTIVITY_LOG_FILE.write_text("line1\nline2", encoding="utf-8")
    activity_log.clear_entries()
    assert activity_log.ACTIVITY_LOG_FILE.read_text(encoding="utf-8") == ""
