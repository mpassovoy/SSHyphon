from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

from .activity_log import log_event
from .models import (
    ConfigResponse,
    JellyfinConfig,
    JellyfinConfigResponse,
    JellyfinSelectedTask,
    SftpConfig,
)

PASSWORD_MASK = "********"

_DATA_DIR = Path(os.getenv("SYNC_MONITOR_DATA_DIR", Path.cwd() / "data")).resolve()
_DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = _DATA_DIR / "config.json"
SECRETS_FILE = _DATA_DIR / "secrets.json"
LAST_SYNC_FILE = _DATA_DIR / "last_sync.txt"
ERROR_LOG_FILE = _DATA_DIR / "sync_errors.log"
JELLYFIN_CONFIG_FILE = _DATA_DIR / "jellyfin_config.json"
AUTH_FILE = _DATA_DIR / "auth.json"

_DEFAULT_CONFIG = SftpConfig().model_dump()
_lock = threading.RLock()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2))


def _secret_identifier(config: dict[str, Any]) -> str:
    host = (config.get("host") or "").strip()
    username = (config.get("username") or "").strip()
    port = config.get("port", 22)
    if not host or not username:
        return "__default__"
    return f"{username}@{host}:{port}"


def _load_secrets() -> dict[str, Any]:
    return _read_json(SECRETS_FILE, {})


def _save_secrets(secrets: dict[str, Any]) -> None:
    _write_json(SECRETS_FILE, secrets)


def _set_password(identifier: str, password: str) -> None:
    secrets = _load_secrets()
    bucket = secrets.setdefault("sftp_passwords", {})
    if password:
        bucket[identifier] = password
    else:
        bucket.pop(identifier, None)
    if not bucket:
        secrets.pop("sftp_passwords", None)
    _save_secrets(secrets)


def _get_password(identifier: str) -> str:
    secrets = _load_secrets().get("sftp_passwords", {})
    return secrets.get(identifier, "")


def normalize_jellyfin_url(raw_url: str) -> str:
    url = (raw_url or "").strip()
    if not url:
        return ""
    if not url.lower().startswith(("http://", "https://")):
        url = "http://" + url
    return url.rstrip("/")


def _jellyfin_identifier(url: str) -> str:
    return normalize_jellyfin_url(url)


def _set_jellyfin_key(identifier: str, api_key: str) -> None:
    secrets = _load_secrets()
    bucket = secrets.setdefault("jellyfin_api_keys", {})
    if api_key:
        bucket[identifier] = api_key
    else:
        bucket.pop(identifier, None)
    if not bucket:
        secrets.pop("jellyfin_api_keys", None)
    _save_secrets(secrets)


def _get_jellyfin_key(identifier: str) -> str:
    secrets = _load_secrets().get("jellyfin_api_keys", {})
    return secrets.get(identifier, "")


def get_config(mask_secrets: bool = True) -> ConfigResponse:
    with _lock:
        if not CONFIG_FILE.exists():
            _write_json(CONFIG_FILE, {**_DEFAULT_CONFIG})
        stored = _read_json(CONFIG_FILE, {})
        data = {**_DEFAULT_CONFIG, **stored}
        identifier = _secret_identifier(data)
        password = _get_password(identifier)
        data["password"] = PASSWORD_MASK if (mask_secrets and password) else password
        has_password = bool(password)
        last_sync_time = get_last_sync_time()
        return ConfigResponse(**data, has_password=has_password, last_sync_time=last_sync_time)


def save_config(new_config: SftpConfig) -> ConfigResponse:
    with _lock:
        previous_raw = _read_json(CONFIG_FILE, {})
        previous_identifier = _secret_identifier(previous_raw)
        previous_password = _get_password(previous_identifier) if previous_identifier else ""
        payload = new_config.model_dump()
        identifier = _secret_identifier(payload)
        raw_password = payload.get("password") or ""
        if raw_password == PASSWORD_MASK:
            if previous_password:
                _set_password(identifier, previous_password)
        elif raw_password:
            _set_password(identifier, raw_password)
        elif not raw_password:
            _set_password(identifier, "")
        if previous_identifier and previous_identifier != identifier:
            _set_password(previous_identifier, "")
        payload["password"] = ""
        _write_json(CONFIG_FILE, payload)
        log_event(
            "sftp.config_saved",
            host=payload.get("host"),
            username=payload.get("username"),
            remote_root=payload.get("remote_root"),
            auto_sync=new_config.auto_sync_enabled,
        )
        return get_config(mask_secrets=True)


def export_unmasked_config() -> SftpConfig:
    with _lock:
        masked = get_config(mask_secrets=False)
        payload = masked.model_dump()
        payload.pop("has_password", None)
        payload.pop("last_sync_time", None)
        return SftpConfig(**payload)


def get_password_for_config(config: SftpConfig) -> str:
    identifier = _secret_identifier(config.model_dump())
    stored = _get_password(identifier)
    if stored:
        return stored
    provided = config.password
    return "" if provided == PASSWORD_MASK else provided


def record_last_sync(timestamp: Optional[float] = None) -> None:
    ts = timestamp or time.time()
    LAST_SYNC_FILE.write_text(str(ts))


def get_last_sync_time() -> Optional[float]:
    if not LAST_SYNC_FILE.exists():
        return None
    try:
        return float(LAST_SYNC_FILE.read_text().strip())
    except Exception:
        return None


def append_error(msg: str) -> None:
    ERROR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with ERROR_LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} - {msg}\n")


def tail_errors(limit: int = 200) -> list[str]:
    if not ERROR_LOG_FILE.exists():
        return []
    lines = ERROR_LOG_FILE.read_text().splitlines()
    return lines[-limit:]


def get_jellyfin_config(mask_secrets: bool = True) -> JellyfinConfigResponse:
    with _lock:
        if not JELLYFIN_CONFIG_FILE.exists():
            default = JellyfinConfig().model_dump()
            JELLYFIN_CONFIG_FILE.write_text(json.dumps(default, indent=2))
        stored = _read_json(JELLYFIN_CONFIG_FILE, {})
        _upgrade_selected_tasks(stored)
        data = JellyfinConfig().model_dump()
        data.update(stored)
        data["server_url"] = normalize_jellyfin_url(data.get("server_url", ""))
        identifier = _jellyfin_identifier(data.get("server_url", ""))
        api_key = _get_jellyfin_key(identifier) if identifier else ""
        data["api_key"] = PASSWORD_MASK if (mask_secrets and api_key) else api_key
        has_api_key = bool(api_key)
        return JellyfinConfigResponse(**data, has_api_key=has_api_key)


def save_jellyfin_config(new_config: JellyfinConfig) -> JellyfinConfigResponse:
    with _lock:
        previous_raw = _read_json(JELLYFIN_CONFIG_FILE, {})
        previous_identifier = _jellyfin_identifier(previous_raw.get("server_url", ""))
        previous_key = _get_jellyfin_key(previous_identifier) if previous_identifier else ""

        payload = new_config.model_dump()
        _upgrade_selected_tasks(payload)
        payload["server_url"] = normalize_jellyfin_url(payload.get("server_url", ""))
        identifier = _jellyfin_identifier(payload.get("server_url", ""))
        raw_key = payload.get("api_key") or ""

        if raw_key == PASSWORD_MASK:
            if previous_key and identifier == previous_identifier:
                _set_jellyfin_key(identifier, previous_key)
            else:
                _set_jellyfin_key(identifier, "")
        elif raw_key:
            _set_jellyfin_key(identifier, raw_key)
        else:
            _set_jellyfin_key(identifier, "")

        if previous_identifier and previous_identifier != identifier:
            _set_jellyfin_key(previous_identifier, "")

        payload["api_key"] = ""
        _write_json(JELLYFIN_CONFIG_FILE, payload)
        log_event(
            "jellyfin.config_saved",
            server_url=payload.get("server_url"),
            include_hidden=payload.get("include_hidden_tasks"),
            selected_tasks=len(payload.get("selected_tasks", [])),
        )
        return get_jellyfin_config(mask_secrets=True)


def get_jellyfin_api_key(config: JellyfinConfig) -> str:
    identifier = _jellyfin_identifier(config.server_url)
    if not identifier:
        return ""
    stored = _get_jellyfin_key(identifier)
    if stored:
        return stored
    provided = config.api_key
    return "" if provided == PASSWORD_MASK else provided


def set_jellyfin_tested(value: bool) -> None:
    with _lock:
        if not JELLYFIN_CONFIG_FILE.exists():
            _write_json(JELLYFIN_CONFIG_FILE, JellyfinConfig().model_dump())
        stored = _read_json(JELLYFIN_CONFIG_FILE, JellyfinConfig().model_dump())
        stored["tested"] = bool(value)
        _write_json(JELLYFIN_CONFIG_FILE, stored)
        log_event("jellyfin.test_status", tested=bool(value), server_url=stored.get("server_url"))


def _upgrade_selected_tasks(data: dict) -> None:
    tasks = data.get("selected_tasks")
    if not isinstance(tasks, list):
        return
    for entry in tasks:
        if not isinstance(entry, dict):
            continue
        if "key" not in entry and "id" in entry:
            entry["legacy_id"] = entry.get("id")
        entry["key"] = entry.get("key") or entry.get("legacy_id") or entry.get("name") or entry.get("id") or ""
        entry.pop("id", None)


def get_auth_record() -> dict[str, Any]:
    with _lock:
        return _read_json(AUTH_FILE, {})


def save_auth_record(payload: dict[str, Any]) -> None:
    with _lock:
        _write_json(AUTH_FILE, payload)
