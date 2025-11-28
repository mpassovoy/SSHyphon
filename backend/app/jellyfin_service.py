from __future__ import annotations

import time
import urllib.parse
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

import requests

from .activity_log import log_event
from .config_store import (
    get_jellyfin_api_key,
    get_jellyfin_config,
    normalize_jellyfin_url,
    set_jellyfin_tested,
)
from .models import JellyfinConfig, JellyfinSelectedTask, JellyfinTask, JellyfinTestRequest


@dataclass
class JellyfinSession:
    base_url: str
    headers: dict

    def get(self, path: str, timeout: int = 20) -> requests.Response:
        url = urllib.parse.urljoin(self.base_url + "/", path.lstrip("/"))
        resp = requests.get(url, headers=self.headers, timeout=timeout)
        return resp

    def post(self, path: str, timeout: int = 20) -> requests.Response:
        url = urllib.parse.urljoin(self.base_url + "/", path.lstrip("/"))
        resp = requests.post(url, headers=self.headers, timeout=timeout)
        return resp

    def delete(self, path: str, timeout: int = 20) -> requests.Response:
        url = urllib.parse.urljoin(self.base_url + "/", path.lstrip("/"))
        resp = requests.delete(url, headers=self.headers, timeout=timeout)
        return resp

def _build_session(server_url: str, api_key: str) -> JellyfinSession:
    url = normalize_jellyfin_url(server_url)
    if not url:
        raise RuntimeError("Jellyfin server URL is missing.")
    if not api_key:
        raise RuntimeError("Jellyfin API key is missing.")
    headers = {"X-Emby-Token": api_key} if api_key else {}
    return JellyfinSession(base_url=url, headers=headers)


def _build_session_from_config(cfg: JellyfinConfig, *, override_api_key: Optional[str] = None) -> JellyfinSession:
    api_key = override_api_key or get_jellyfin_api_key(cfg)
    return _build_session(cfg.server_url, api_key)


def test_connection(payload: Optional[JellyfinTestRequest] = None) -> None:
    if payload:
        session = _build_session(payload.server_url, payload.api_key)
        _fetch_task_map(session, include_hidden=payload.include_hidden_tasks)
        if payload.persist:
            set_jellyfin_tested(True)
        log_event("jellyfin.test_success", server_url=payload.server_url)
        return
    cfg_resp = get_jellyfin_config(mask_secrets=False)
    cfg = JellyfinConfig(**cfg_resp.model_dump())
    session = _build_session_from_config(cfg)
    _fetch_task_map(session, include_hidden=True)
    set_jellyfin_tested(True)
    log_event("jellyfin.test_success", server_url=cfg.server_url)


def list_tasks() -> list[JellyfinTask]:
    cfg_resp = get_jellyfin_config(mask_secrets=False)
    cfg = JellyfinConfig(**cfg_resp.model_dump())
    session = _build_session_from_config(cfg)
    raw_map = _fetch_task_map(session, include_hidden=cfg.include_hidden_tasks, return_raw=True)
    tasks: list[JellyfinTask] = []
    for raw in raw_map.values():
        tasks.append(
            JellyfinTask(
                id=str(raw["Id"]),
                key=str(raw.get("Key") or raw["Id"]),
                name=str(raw["Name"]),
                description=raw.get("Description"),
                is_hidden=bool(raw.get("IsHidden", False)),
            )
        )
    return tasks


def start_selected_tasks(tasks: Iterable[str]) -> None:
    cfg_resp = get_jellyfin_config(mask_secrets=False)
    cfg = JellyfinConfig(**cfg_resp.model_dump())
    session = _build_session_from_config(cfg)
    for task_id in tasks or []:
        _start_task(session, task_id, task_id)


def _get_ordered_selected_tasks(cfg: JellyfinConfig) -> list[JellyfinSelectedTask]:
    selected = [task for task in cfg.selected_tasks if task.enabled]
    if not selected:
        raise RuntimeError("No Jellyfin tasks have been selected.")
    selected.sort(key=lambda t: t.order)
    return selected


def run_selected_tasks(
    stop_event,
    progress_callback: Callable[[str, float, str, int, int], None],
    poll_interval: float = 1.0,
) -> None:
    cfg_resp = get_jellyfin_config(mask_secrets=False)
    cfg = JellyfinConfig(**cfg_resp.model_dump())
    tasks = _get_ordered_selected_tasks(cfg)
    session = _build_session_from_config(cfg)
    raw_map = _fetch_task_map(session, include_hidden=cfg.include_hidden_tasks, return_raw=True)
    key_map = {task.get("Key") or task["Id"]: task for task in raw_map.values()}
    name_map = {task["Name"]: task for task in raw_map.values()}
    id_map = {task["Id"]: task for task in raw_map.values()}
    total = len(tasks)

    log_event("jellyfin.run_start", total_tasks=len(tasks))
    for index, task in enumerate(tasks, 1):
        if stop_event.is_set():
            raise RuntimeError("Jellyfin run cancelled.")
        progress_callback(task.name, 0.0, "Starting", index, total)
        log_event("jellyfin.task_start", name=task.name, order=index)
        task_info = (
            key_map.get(task.key)
            or name_map.get(task.name)
            or (task.legacy_id and id_map.get(task.legacy_id))
        )
        if not task_info:
            raise RuntimeError(f"Task '{task.name}' was not found on the server.")
        task_id = task_info["Id"]
        _start_task(session, task_id, task.name)
        consecutive_errors = 0
        while True:
            if stop_event.is_set():
                try:
                    _cancel_task(session, task_id, task.name)
                except Exception:
                    pass
                raise RuntimeError("Jellyfin run cancelled.")
            try:
                status = _get_task_status(session, task_id)
            except requests.RequestException as exc:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    raise RuntimeError(f"Failed to poll '{task.name}': {exc}") from exc
                time.sleep(poll_interval * 2)
                continue
            consecutive_errors = 0
            progress = float(status.get("CurrentProgressPercentage") or 0.0)
            state = status.get("State") or "Unknown"
            progress_callback(task.name, progress, state, index, total)
            if progress >= 100 or state.lower() in ("idle", "completed", "completedwitherrors"):
                log_event("jellyfin.task_complete", name=task.name, progress=progress, state=state)
                break
            time.sleep(poll_interval)
    log_event("jellyfin.run_finish", total_tasks=len(tasks))


def _fetch_task_map(session: JellyfinSession, include_hidden: bool, return_raw: bool = False) -> dict:
    resp = session.get("/ScheduledTasks")
    resp.raise_for_status()
    mapping: dict = {}
    for task in resp.json():
        if not include_hidden and task.get("IsHidden", False):
            continue
        key = task.get("Key") or task.get("Id")
        if not key:
            continue
        mapping[key] = task if return_raw else task.get("Id")
    return mapping


def _start_task(session: JellyfinSession, task_id: str, task_name: str) -> None:
    resp = session.post(f"/ScheduledTasks/Running/{task_id}")
    if resp.status_code != 204:
        raise RuntimeError(f"Failed to start '{task_name}': {resp.status_code} {resp.text.strip()}")


def _cancel_task(session: JellyfinSession, task_id: str, task_name: str) -> None:
    try:
        resp = session.delete(f"/ScheduledTasks/Running/{task_id}")
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to cancel '{task_name}': {exc}") from exc
    if resp.status_code not in (200, 202, 204, 404):
        raise RuntimeError(f"Failed to cancel '{task_name}': {resp.status_code} {resp.text.strip()}")


def _get_task_status(session: JellyfinSession, task_id: str) -> dict:
    resp = session.get(f"/ScheduledTasks/{task_id}")
    if resp.status_code == 404:
        return {"CurrentProgressPercentage": 100, "State": "Completed"}
    resp.raise_for_status()
    return resp.json()
