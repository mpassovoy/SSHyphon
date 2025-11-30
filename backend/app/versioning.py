from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from time import time
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = PROJECT_ROOT / "VERSION"
VERSION_JSON_FILE = PROJECT_ROOT / "VERSION.json"
GITHUB_REPO_ENV = "SSHPHON_GITHUB_REPOSITORY"
FALLBACK_GITHUB_REPO = "mpassovoy/SSHyphon"
_CACHE_TTL_SECONDS = 300
_cached_payload: dict[str, Any] | None = None
_cached_at: float | None = None
_cached_metadata_signature: str | None = None


def read_version(default: str = "0.0.0") -> str:
    """Read the canonical VERSION file."""
    try:
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
        return version or default
    except FileNotFoundError:
        return default


def read_version_metadata() -> dict[str, Any]:
    canonical_version = read_version()
    metadata: dict[str, Any] = {"version": canonical_version}
    if VERSION_JSON_FILE.exists():
        try:
            metadata.update(json.loads(VERSION_JSON_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    metadata["version"] = canonical_version
    return metadata


def _normalize_version_string(tag: str | None) -> str | None:
    if not tag:
        return None
    cleaned = tag.strip()
    if cleaned.startswith("v"):
        cleaned = cleaned[1:]
    return cleaned if cleaned else None


def _parse_version_tuple(value: str | None) -> tuple[int, ...]:
    if not value:
        return tuple()
    parts = re.split(r"\D", value)
    return tuple(int(p) for p in parts if p.isdigit())


def _infer_repository_slug() -> str | None:
    env_repo = os.getenv(GITHUB_REPO_ENV) or os.getenv("GITHUB_REPOSITORY")
    if env_repo:
        return env_repo

    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return FALLBACK_GITHUB_REPO

    url = result.stdout.strip()
    if not url:
        return FALLBACK_GITHUB_REPO

    if url.endswith(".git"):
        url = url[:-4]
    if "github.com" in url:
        if url.startswith("git@"):
            _, remainder = url.split(":", 1)
            return remainder
        if url.startswith("https://"):
            parts = url.split("github.com/", 1)
            if len(parts) == 2:
                return parts[1]
    return FALLBACK_GITHUB_REPO


def fetch_latest_version_tag(repo_slug: str) -> str | None:
    if not repo_slug:
        return None

    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}".strip()

    try:
        release_resp = requests.get(
            f"https://api.github.com/repos/{repo_slug}/releases/latest",
            headers=headers,
            timeout=5,
        )
        if release_resp.ok:
            try:
                tag_name = release_resp.json().get("tag_name")
            except ValueError:
                tag_name = None
            normalized = _normalize_version_string(tag_name)
            if normalized:
                return normalized
    except requests.RequestException:
        return None

    try:
        tags_resp = requests.get(
            f"https://api.github.com/repos/{repo_slug}/tags",
            headers=headers,
            params={"per_page": 1},
            timeout=5,
        )
        if tags_resp.ok:
            try:
                tags = tags_resp.json()
            except ValueError:
                tags = None
            if tags:
                return _normalize_version_string(tags[0].get("name"))
    except requests.RequestException:
        return None

    return None


def is_update_available(current: str | None, latest: str | None) -> bool:
    if not current or not latest:
        return False
    return _parse_version_tuple(latest) > _parse_version_tuple(current)


def clear_version_cache() -> None:
    """Reset cached version payload (primarily for tests)."""

    global _cached_payload, _cached_at, _cached_metadata_signature
    _cached_payload = None
    _cached_at = None
    _cached_metadata_signature = None


def get_version_payload() -> dict[str, Any]:
    global _cached_payload, _cached_at, _cached_metadata_signature

    metadata = read_version_metadata()
    metadata_signature = json.dumps(metadata, sort_keys=True)
    now = time()

    if (
        _cached_payload is not None
        and _cached_at is not None
        and now - _cached_at <= _CACHE_TTL_SECONDS
        and _cached_metadata_signature == metadata_signature
    ):
        return _cached_payload

    payload = metadata
    repo_slug = _infer_repository_slug()
    payload["repository"] = repo_slug

    latest_version = fetch_latest_version_tag(repo_slug) if repo_slug else None
    payload["latest_version"] = latest_version
    payload["update_available"] = is_update_available(payload.get("version"), latest_version)
    payload.setdefault("checked_at", datetime.utcnow().isoformat() + "Z")

    _cached_payload = payload
    _cached_at = now
    _cached_metadata_signature = metadata_signature
    return payload

