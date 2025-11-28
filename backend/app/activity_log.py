from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

_DATA_ROOT = Path(os.getenv("SYNC_MONITOR_DATA_DIR", Path.cwd() / "data")).resolve()
_DATA_ROOT.mkdir(parents=True, exist_ok=True)
ACTIVITY_LOG_FILE = _DATA_ROOT / "activity.log"

_LOGGER = logging.getLogger("sync_monitor.activity")
if not _LOGGER.handlers:
    _LOGGER.setLevel(logging.INFO)
    handler = logging.FileHandler(ACTIVITY_LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    _LOGGER.addHandler(handler)
    _LOGGER.propagate = False


def _serialize(payload: Mapping[str, Any]) -> str:
    try:
        return json.dumps(payload, default=str, ensure_ascii=False)
    except Exception:
        return str(payload)


def log_event(action: str, **details: Any) -> None:
    message = {"action": action, **details}
    _LOGGER.info(_serialize(message))


def log_warning(action: str, **details: Any) -> None:
    message = {"action": action, **details}
    _LOGGER.warning(_serialize(message))


def log_error(action: str, **details: Any) -> None:
    message = {"action": action, **details}
    _LOGGER.error(_serialize(message))


def read_entries(limit: int = 1000) -> list[str]:
    if not ACTIVITY_LOG_FILE.exists():
        return []
    try:
        lines = ACTIVITY_LOG_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    return lines[-limit:]


def clear_entries() -> None:
    ACTIVITY_LOG_FILE.write_text("", encoding="utf-8")
