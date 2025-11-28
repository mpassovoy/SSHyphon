import argparse
import sys
import time
import urllib.parse
from typing import Iterable

import requests

sys.path.append(str((__file__).rsplit("/backend/", 1)[0] + "/backend"))

from app import config_store  # type: ignore  # noqa: E402
from app.models import JellyfinConfig  # type: ignore  # noqa: E402


def normalize_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    if not value.lower().startswith(("http://", "https://")):
        value = "http://" + value
    return value.rstrip("/")


def _build_headers(api_key: str) -> dict:
    if not api_key:
        raise RuntimeError("An API key is required.")
    return {"X-Emby-Token": api_key}


def fetch_task_map(base_url: str, api_key: str, include_hidden: bool) -> dict[str, dict]:
    endpoint = urllib.parse.urljoin(base_url + "/", "ScheduledTasks")
    resp = requests.get(endpoint, headers=_build_headers(api_key), timeout=20)
    resp.raise_for_status()
    mapping: dict[str, dict] = {}
    for task in resp.json():
        if not include_hidden and task.get("IsHidden", False):
            continue
        key = task.get("Key") or task.get("Id")
        if not key:
            continue
        mapping[str(key)] = task
    return mapping


def start_task(base_url: str, api_key: str, task_id: str, task_name: str) -> None:
    url = urllib.parse.urljoin(base_url + "/", f"ScheduledTasks/Running/{task_id}")
    resp = requests.post(url, headers=_build_headers(api_key), timeout=30)
    if resp.status_code != 204:
        raise RuntimeError(f"Failed to start '{task_name}': {resp.status_code} {resp.text.strip()}")


def poll_task(base_url: str, api_key: str, task_id: str) -> dict:
    url = urllib.parse.urljoin(base_url + "/", f"ScheduledTasks/{task_id}")
    resp = requests.get(url, headers=_build_headers(api_key), timeout=30)
    if resp.status_code == 404:
        return {"CurrentProgressPercentage": 100, "State": "Completed"}
    resp.raise_for_status()
    return resp.json()


def run_tasks(
    base_url: str,
    api_key: str,
    task_keys: Iterable[str],
    include_hidden: bool,
    poll_interval: float,
) -> None:
    print(f"Connecting to Jellyfin at {base_url}")
    mapping = fetch_task_map(base_url, api_key, include_hidden)
    ordered = []
    for key in task_keys:
        entry = mapping.get(key)
        if entry:
            ordered.append(entry)
    if not ordered:
        raise RuntimeError("No matching tasks were found in Jellyfin.")

    total = len(ordered)
    for index, entry in enumerate(ordered, 1):
        name = entry.get("Name") or entry.get("Key") or entry.get("Id")
        task_id = entry.get("Id")
        if not task_id:
            continue
        print(f"[{index}/{total}] Starting '{name}' (key={entry.get('Key')})")
        start_task(base_url, api_key, task_id, name)
        while True:
            status = poll_task(base_url, api_key, task_id)
            progress = float(status.get("CurrentProgressPercentage") or 0.0)
            state = status.get("State") or "Unknown"
            print(f"    {name}: {progress:.1f}% ({state})")
            if progress >= 100 or state.lower() in ("idle", "completed", "completedwitherrors"):
                break
            time.sleep(poll_interval)
        print(f"[{index}/{total}] '{name}' completed.")


def main():
    parser = argparse.ArgumentParser(description="Debug Jellyfin scheduled tasks.")
    parser.add_argument("--server-url", help="Override Jellyfin server URL")
    parser.add_argument("--api-key", help="Override Jellyfin API key")
    parser.add_argument("--tasks", nargs="+", help="Task keys to run (defaults to selected tasks in config)")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden tasks when resolving keys")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds (default: 1.0)")
    args = parser.parse_args()

    cfg_response = config_store.get_jellyfin_config(mask_secrets=not bool(args.api_key))
    cfg = JellyfinConfig(**cfg_response.model_dump())
    server_url = normalize_url(args.server_url or cfg.server_url)
    api_key = args.api_key or config_store.get_jellyfin_api_key(cfg)

    if not server_url:
        raise SystemExit("Please provide --server-url or save the Jellyfin URL in the UI.")
    if not api_key:
        raise SystemExit("Please provide --api-key or save the Jellyfin API key in the UI.")

    tasks = args.tasks or [task.key for task in cfg.selected_tasks if task.enabled and task.key]
    if not tasks:
        raise SystemExit("No task keys specified and none are selected in the config.")

    run_tasks(server_url, api_key, tasks, include_hidden=args.include_hidden, poll_interval=args.interval)


if __name__ == "__main__":
    main()
