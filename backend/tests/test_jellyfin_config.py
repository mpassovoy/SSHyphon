import importlib

import pytest

from backend.app import config_store
from backend.app.models import JellyfinConfig


@pytest.fixture
def jellyfin_store(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNC_MONITOR_DATA_DIR", str(tmp_path))
    importlib.reload(config_store)
    yield config_store
    importlib.reload(config_store)


def test_jellyfin_url_normalization(jellyfin_store):
    resp = jellyfin_store.save_jellyfin_config(JellyfinConfig(server_url="example.com/", api_key="secret"))
    assert resp.server_url == "http://example.com"
    assert resp.api_key == jellyfin_store.PASSWORD_MASK

    file_contents = jellyfin_store.JELLYFIN_CONFIG_FILE.read_text()
    assert "http://example.com" in file_contents

    fetched = jellyfin_store.get_jellyfin_config()
    assert fetched.server_url == "http://example.com"
    assert fetched.api_key == jellyfin_store.PASSWORD_MASK


def test_api_key_masking_and_url_change(jellyfin_store):
    initial = jellyfin_store.save_jellyfin_config(
        JellyfinConfig(server_url="demo.local", api_key="abc123", selected_tasks=[])
    )
    assert initial.api_key == jellyfin_store.PASSWORD_MASK
    assert initial.has_api_key is True

    preserved = jellyfin_store.save_jellyfin_config(
        JellyfinConfig(server_url="http://demo.local/", api_key=jellyfin_store.PASSWORD_MASK)
    )
    assert preserved.api_key == jellyfin_store.PASSWORD_MASK
    assert preserved.has_api_key is True
    unmasked = jellyfin_store.get_jellyfin_config(mask_secrets=False)
    assert unmasked.api_key == "abc123"

    changed = jellyfin_store.save_jellyfin_config(
        JellyfinConfig(server_url="other.local/", api_key=jellyfin_store.PASSWORD_MASK)
    )
    assert changed.api_key == ""
    assert changed.has_api_key is False
    assert jellyfin_store._get_jellyfin_key(jellyfin_store._jellyfin_identifier("http://demo.local")) == ""


def test_upgrade_selected_tasks_preserves_entries(jellyfin_store):
    payload = {
        "selected_tasks": [
            {"key": "task-a", "name": "Task A", "enabled": True},
            {"id": "legacy-id", "name": "Legacy", "enabled": False},
        ]
    }
    jellyfin_store._upgrade_selected_tasks(payload)

    first, second = payload["selected_tasks"]
    assert first["key"] == "task-a"
    assert "legacy_id" in second
    assert second["key"] == "legacy-id"
    assert "id" not in second
