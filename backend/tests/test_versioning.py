import json
import time
from pathlib import Path

import pytest

from backend.app import versioning


@pytest.fixture(autouse=True)
def clear_cache():
    versioning.clear_version_cache()
    yield
    versioning.clear_version_cache()


def test_normalize_and_parse_helpers():
    assert versioning._normalize_version_string("v1.2.3") == "1.2.3"
    assert versioning._normalize_version_string(" 2.0.0 ") == "2.0.0"
    assert versioning._normalize_version_string("") is None
    assert versioning._parse_version_tuple("1.2.3") == (1, 2, 3)
    assert versioning._parse_version_tuple("1.a.10") == (1, 10)


def test_update_available_comparison():
    assert versioning.is_update_available("1.0.0", "1.0.1") is True
    assert versioning.is_update_available("1.0.1", "1.0.0") is False
    assert versioning.is_update_available(None, "1.0.0") is False
    assert versioning.is_update_available("1.0.0", None) is False


def test_get_version_payload_caches_and_invalidates(tmp_path, monkeypatch):
    version_file = tmp_path / "VERSION"
    version_json = tmp_path / "VERSION.json"
    version_file.write_text("1.0.0\n", encoding="utf-8")
    version_json.write_text(json.dumps({"version": "1.0.0", "commit": "abc"}), encoding="utf-8")

    monkeypatch.setattr(versioning, "VERSION_FILE", version_file)
    monkeypatch.setattr(versioning, "VERSION_JSON_FILE", version_json)
    monkeypatch.setattr(versioning, "_infer_repository_slug", lambda: "example/repo")

    calls = {"count": 0}

    def fake_fetch(repo: str) -> str:
        calls["count"] += 1
        return "1.1.0"

    monkeypatch.setattr(versioning, "fetch_latest_version_tag", fake_fetch)

    first_payload = versioning.get_version_payload()
    assert first_payload["version"] == "1.0.0"
    assert first_payload["latest_version"] == "1.1.0"
    assert first_payload["update_available"] is True
    assert calls["count"] == 1

    # Second call should use cached payload when files unchanged
    second_payload = versioning.get_version_payload()
    assert second_payload is first_payload
    assert calls["count"] == 1

    time.sleep(1.1)
    version_file.write_text("2.0.0\n", encoding="utf-8")

    refreshed_payload = versioning.get_version_payload()
    assert refreshed_payload["version"] == "2.0.0"
    assert calls["count"] == 2
