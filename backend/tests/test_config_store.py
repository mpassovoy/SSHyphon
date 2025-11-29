import importlib
import json

import backend.app.config_store as config_store


def _reload_store(tmp_path, monkeypatch, *, config=None, secrets=None, jellyfin_config=None):
    monkeypatch.setenv("SYNC_MONITOR_DATA_DIR", str(tmp_path))

    if config is not None:
        (tmp_path / "config.json").write_text(json.dumps(config))
    if secrets is not None:
        (tmp_path / "secrets.json").write_text(json.dumps(secrets))
    if jellyfin_config is not None:
        (tmp_path / "jellyfin_config.json").write_text(json.dumps(jellyfin_config))

    reloaded = importlib.reload(config_store)
    monkeypatch.setattr(reloaded, "log_event", lambda *args, **kwargs: None)
    return reloaded


def test_save_config_keeps_existing_secret_when_masked(tmp_path, monkeypatch):
    identifier = "demo@example.com:22"
    store = _reload_store(
        tmp_path,
        monkeypatch,
        config={
            "host": "example.com",
            "username": "demo",
            "remote_root": "/remote",
            "local_root": "/local",
            "password": "",
            "skip_folders": ["cache"],
        },
        secrets={"sftp_passwords": {identifier: "supersecret"}},
    )

    masked_update = store.SftpConfig(
        host="example.com",
        username="demo",
        password=store.PASSWORD_MASK,
        remote_root="/remote",
        local_root="/local",
        skip_folders=["cache", "tmp"],
        auto_sync_enabled=True,
    )
    response = store.save_config(masked_update)

    identifier = store._secret_identifier(masked_update.model_dump())
    assert store._get_password(identifier) == "supersecret"
    assert response.password == store.PASSWORD_MASK
    assert response.has_password is True

    exported = store.export_unmasked_config()
    exported_payload = exported.model_dump()
    assert exported_payload["password"] == "supersecret"
    assert "has_password" not in exported_payload
    assert "last_sync_time" not in exported_payload


def test_save_config_reassigns_password_when_identifier_changes(tmp_path, monkeypatch):
    store = _reload_store(tmp_path, monkeypatch)

    original = store.SftpConfig(
        host="first.example.com",
        username="alice",
        password="oldpass",
        remote_root="/remote",
        local_root="/local",
    )
    store.save_config(original)
    old_identifier = store._secret_identifier(original.model_dump())

    updated = store.SftpConfig(
        host="second.example.com",
        username="bob",
        password="newpass",
        remote_root="/remote",
        local_root="/local",
    )
    response = store.save_config(updated)
    new_identifier = store._secret_identifier(updated.model_dump())

    assert store._get_password(new_identifier) == "newpass"
    assert store._get_password(old_identifier) == ""
    assert response.password == store.PASSWORD_MASK
    assert response.has_password is True


def test_get_password_for_config_handles_masks(tmp_path, monkeypatch):
    identifier = "demo@example.com:22"
    store = _reload_store(
        tmp_path,
        monkeypatch,
        config={"host": "example.com", "username": "demo"},
        secrets={"sftp_passwords": {identifier: "storedpass"}},
    )

    masked_config = store.SftpConfig(host="example.com", username="demo", password=store.PASSWORD_MASK)
    assert store.get_password_for_config(masked_config) == "storedpass"

    provided_config = store.SftpConfig(host="example.com", username="other", password="provided")
    assert store.get_password_for_config(provided_config) == "provided"

    missing_config = store.SftpConfig(host="other", username="user", password=store.PASSWORD_MASK)
    assert store.get_password_for_config(missing_config) == ""


def test_normalize_and_store_jellyfin_secrets(tmp_path, monkeypatch):
    previous_identifier = "http://media.example.com"
    secrets = {"jellyfin_api_keys": {previous_identifier: "abc123"}}
    store = _reload_store(
        tmp_path,
        monkeypatch,
        jellyfin_config={"server_url": "media.example.com"},
        secrets=secrets,
    )

    assert store.normalize_jellyfin_url("media.example.com/") == "http://media.example.com"
    assert store.normalize_jellyfin_url("https://demo.local//") == "https://demo.local"
    assert store._jellyfin_identifier("media.example.com") == "http://media.example.com"

    masked = store.JellyfinConfig(server_url="media.example.com/", api_key=store.PASSWORD_MASK)
    response = store.save_jellyfin_config(masked)
    assert response.api_key == store.PASSWORD_MASK
    assert response.has_api_key is True
    assert store._get_jellyfin_key(previous_identifier) == "abc123"

    changed = store.JellyfinConfig(server_url="https://new.example.com", api_key=store.PASSWORD_MASK)
    updated = store.save_jellyfin_config(changed)
    new_identifier = store._jellyfin_identifier("https://new.example.com")
    assert updated.has_api_key is False
    assert store._get_jellyfin_key(previous_identifier) == ""
    assert store._get_jellyfin_key(new_identifier) == ""


def test_append_and_tail_errors(tmp_path, monkeypatch):
    store = _reload_store(tmp_path, monkeypatch)

    store.append_error("first error")
    store.append_error("second error")
    store.append_error("third error")

    full_log = store.tail_errors()
    assert len(full_log) == 3
    assert full_log[0].endswith("first error")

    trimmed = store.tail_errors(limit=2)
    assert trimmed == full_log[-2:]
