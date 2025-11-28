from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from . import config_store
from .activity_log import log_event
from .models import SftpConfig
from .sync_service import (
    MissingCredentialsError,
    SyncInProgressError,
    sync_service,
)

LOGGER = logging.getLogger("uvicorn.error")


class AutoSyncController:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._config: Optional[SftpConfig] = None
        self._next_run_time: Optional[float] = None

    def update_config(self, config: SftpConfig) -> None:
        copy = config.model_copy(deep=True)
        with self._lock:
            self._config = copy
            if self._next_run_time:
                self._arm_timer_locked(max(copy.sync_interval_minutes, 1) * 60)

    def schedule_next_run(self, config: Optional[SftpConfig] = None) -> None:
        with self._lock:
            if config is not None:
                self._config = config.model_copy(deep=True)
            if not self._config:
                return
            delay_seconds = max(self._config.sync_interval_minutes, 1) * 60
            self._arm_timer_locked(delay_seconds)

    def cancel_schedule(self) -> None:
        with self._lock:
            self._cancel_timer_locked()
            self._next_run_time = None
        sync_service.set_next_sync_time(None)
        log_event("autosync.cancelled")

    def shutdown(self) -> None:
        self.cancel_schedule()
        with self._lock:
            self._config = None

    def ensure_start_on_restart(self) -> None:
        with self._lock:
            config = self._config
        if not config or not config.auto_sync_enabled:
            return
        status = sync_service.status()
        if status.state not in {"idle", "error"}:
            return
        try:
            log_event("autosync.restart_trigger", host=config.host, remote_root=config.remote_root)
            sync_service.start(config)
            self.schedule_next_run(config)
        except SyncInProgressError:
            log_event("autosync.restart_skipped", reason="already_running")
        except MissingCredentialsError as exc:
            log_event("autosync.restart_failed", error=str(exc))
        except Exception as exc:
            log_event("autosync.restart_failed", error=str(exc))

    # Internal helpers ------------------------------------------------------
    def _arm_timer_locked(self, delay_seconds: int) -> None:
        self._cancel_timer_locked()
        self._next_run_time = time.time() + delay_seconds
        timer = threading.Timer(delay_seconds, self._run_scheduled_sync)
        timer.daemon = True
        self._timer = timer
        timer.start()
        next_time = self._next_run_time
        sync_service.set_next_sync_time(next_time)
        log_event("autosync.timer_armed", delay_seconds=delay_seconds, next_time=next_time)

    def _cancel_timer_locked(self) -> None:
        if self._timer:
            self._timer.cancel()
        self._timer = None

    def _schedule_retry(self, delay_seconds: int) -> None:
        delay_seconds = max(delay_seconds, 5)
        with self._lock:
            self._arm_timer_locked(delay_seconds)

    def _run_scheduled_sync(self) -> None:
        config = config_store.export_unmasked_config()
        with self._lock:
            self._config = config.model_copy(deep=True)
        log_event("autosync.run_triggered", host=config.host, remote_root=config.remote_root)
        try:
            sync_service.start(config)
        except SyncInProgressError:
            LOGGER.info("Scheduled sync skipped because a run is already active; retrying soon.")
            self._schedule_retry(30)
            log_event("autosync.run_skipped", reason="sync_in_progress")
            return
        except MissingCredentialsError as exc:
            LOGGER.warning("Scheduled sync cancelled: %s", exc)
            self.cancel_schedule()
            log_event("autosync.run_cancelled", reason=str(exc))
            return
        except Exception as exc:
            LOGGER.exception("Failed to launch scheduled sync: %s", exc)
            interval = max(config.sync_interval_minutes, 1) * 60
            self._schedule_retry(interval)
            log_event("autosync.run_failed", error=str(exc))
            return
        self.schedule_next_run()


controller = AutoSyncController()
