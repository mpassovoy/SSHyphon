from __future__ import annotations

import logging
import os
import stat
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import paramiko
from paramiko import AutoAddPolicy, SSHClient

from . import config_store, jellyfin_service
from .activity_log import log_event, log_error as log_activity_error, log_warning as log_activity_warning
from .models import FileTransfer, SftpConfig, SyncStats, SyncStatus


LOGGER = logging.getLogger("uvicorn.error")


class SyncInProgressError(RuntimeError):
    """Raised when a sync is already running."""


class MissingCredentialsError(RuntimeError):
    """Raised when required SFTP credentials are absent."""


class StopRequested(Exception):
    """Raised internally when a stop has been requested."""


class SyncService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._jellyfin_thread: Optional[threading.Thread] = None
        self._jellyfin_stop_event = threading.Event()
        self._state = SyncStatus()
        self._recent_transfers: deque[FileTransfer] = deque(maxlen=50)
        self._connection_lock = threading.Lock()
        self._ssh_client: Optional[SSHClient] = None
        self._sftp_handle: Optional[paramiko.SFTPClient] = None

    # Public API ----------------------------------------------------------------
    def start(self, config: SftpConfig) -> SyncStatus:
        LOGGER.debug("sync_service.start invoked for host=%s port=%s user=%s", config.host, config.port, config.username)
        password = config_store.get_password_for_config(config)
        if not all([config.host, config.username, password, config.remote_root, config.local_root]):
            raise MissingCredentialsError("Host, username, password, remote root, and local root are required.")

        with self._lock:
            if self._thread and self._thread.is_alive():
                raise SyncInProgressError("A sync is already running.")

            self._stop_event.clear()
            self._state = SyncStatus(
                state="connecting",
                message="Connecting to SFTP…",
                stats=SyncStats(),
                last_sync_time=config_store.get_last_sync_time(),
                recent_transfers=list(self._recent_transfers),
            )
            worker = threading.Thread(
                target=self._run,
                args=(config, password),
                name="sftp-sync-worker",
                daemon=True,
            )
            self._thread = worker

        LOGGER.debug("Launching sync worker thread")
        log_event("sync.start", host=config.host, remote_root=config.remote_root)
        worker.start()
        return self.status()

    def stop(self) -> SyncStatus:
        stop_sftp = False
        stop_jellyfin = False
        with self._lock:
            if self._thread and self._thread.is_alive():
                stop_sftp = True
                self._stop_event.set()
                self._state.state = "stopping"
                self._state.message = "Stopping sync…"
            if self._jellyfin_thread and self._jellyfin_thread.is_alive():
                stop_jellyfin = True
                self._jellyfin_stop_event.set()
                self._state.state = "jellyfin"
                self._state.message = "Stopping Jellyfin tasks…"

        if not (stop_sftp or stop_jellyfin):
            LOGGER.debug("Stop requested but no active worker.")
            return self.status()

        log_event("sync.stop_requested", stop_sftp=stop_sftp, stop_jellyfin=stop_jellyfin)
        if stop_sftp:
            self._close_active_connection()

        return self.status()

    def status(self) -> SyncStatus:
        with self._lock:
            snapshot = self._state.model_copy(deep=True)
            snapshot.recent_transfers = list(self._recent_transfers)
            return snapshot

    def start_jellyfin_tasks(self) -> SyncStatus:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("Cannot run Jellyfin tasks while a sync is active.")
            if self._jellyfin_thread and self._jellyfin_thread.is_alive():
                raise RuntimeError("Jellyfin tasks are already running.")
            cfg = config_store.get_jellyfin_config()
            if not cfg.tested:
                raise RuntimeError("Test the Jellyfin connection first.")
            self._jellyfin_stop_event.clear()
            self._update_state(state="jellyfin", message="Starting Jellyfin tasks…", progress=0, active_file=None)
            worker = threading.Thread(
                target=self._run_jellyfin_tasks,
                name="jellyfin-task-runner",
                daemon=True,
            )
            self._jellyfin_thread = worker
        log_event("jellyfin.run_started")
        worker.start()
        return self.status()

    # Internal helpers ----------------------------------------------------------
    def _run(self, config: SftpConfig, password: str) -> None:
        sftp = None
        LOGGER.debug("Worker thread running: connecting to %s:%s", config.host, config.port)
        client: Optional[SSHClient] = None
        trigger_jellyfin = False
        try:
            client = SSHClient()
            client.set_missing_host_key_policy(AutoAddPolicy())
            LOGGER.debug("Opening SSHClient connection")
            client.connect(
                hostname=config.host,
                port=config.port,
                username=config.username,
                password=password,
                timeout=20,
                banner_timeout=20,
                auth_timeout=20,
                look_for_keys=False,
                allow_agent=False,
            )
            sftp = client.open_sftp()
            self._store_active_connection(client, sftp)
            self._update_state(state="scanning", message="Scanning remote tree…", progress=0)
            LOGGER.debug("SSH handshake completed; starting directory scan.")

            remote_root = config.remote_root.rstrip("/") or "/"
            local_root = Path(config.local_root).expanduser()
            local_root.mkdir(parents=True, exist_ok=True)
            skip_folders = {folder.lower() for folder in config.skip_folders}
            sync_cutoff = self._resolve_sync_cutoff(config)

            self._sync_directory(
                sftp=sftp,
                remote_path=remote_root,
                local_path=local_root,
                skip_folders=skip_folders,
                last_sync_cutoff=sync_cutoff,
            )
            aborted = self._stop_event.is_set()
            trigger_jellyfin = False
            if aborted:
                self._update_state(
                    state="idle",
                    message="Stopped by user",
                    progress=0,
                    active_file=None,
                    target_path=None,
                    download_speed=None,
                )
            else:
                config_store.record_last_sync()
                last_sync_time = config_store.get_last_sync_time()
                self._update_state(
                    state="idle",
                    message="Idle",
                    progress=0,
                    active_file=None,
                    target_path=None,
                    download_speed=None,
                    last_sync_time=last_sync_time,
                )
                trigger_jellyfin = (
                    self._state.stats.files_downloaded > 0 and self._should_run_jellyfin_after_sync()
                )
                log_event(
                    "sync.completed",
                    files_downloaded=self._state.stats.files_downloaded,
                    bytes_downloaded=self._state.stats.bytes_downloaded,
                    errors=self._state.stats.errors,
                    triggered_jellyfin=trigger_jellyfin,
                )
        except StopRequested:
            LOGGER.debug("Stop requested; shutting down worker.")
            self._update_state(
                state="idle",
                message="Stopped by user",
                progress=0,
                active_file=None,
                target_path=None,
                download_speed=None,
            )
        except Exception as exc:
            LOGGER.exception("Sync worker failed: %s", exc)
            self._log_error(str(exc))
            self._update_state(
                state="error",
                message="Sync failed",
                last_error=str(exc),
                progress=0,
                active_file=None,
                target_path=None,
            )
        finally:
            self._close_active_connection()
            with self._lock:
                self._thread = None
                self._stop_event.clear()

        if trigger_jellyfin:
            LOGGER.info("Launching Jellyfin tasks after successful sync.")
            try:
                self.start_jellyfin_tasks()
            except Exception as exc:
                LOGGER.warning("Unable to start Jellyfin tasks after sync: %s", exc)
                log_activity_warning("jellyfin.post_sync_failed", error=str(exc))

    def _run_jellyfin_tasks(self) -> None:
        try:
            jellyfin_service.run_selected_tasks(
                stop_event=self._jellyfin_stop_event,
                progress_callback=self._handle_jellyfin_progress,
            )
            self._update_state(
                state="idle",
                message="Idle",
                progress=0,
                active_file=None,
                target_path=None,
            )
            log_event("jellyfin.run_completed")
        except RuntimeError as exc:
            if "cancelled" in str(exc).lower():
                LOGGER.info("Jellyfin tasks cancelled by user.")
                self._update_state(
                    state="idle",
                    message="Jellyfin tasks cancelled",
                    progress=0,
                    active_file=None,
                    target_path=None,
                )
                log_event("jellyfin.run_cancelled")
            else:
                LOGGER.exception("Jellyfin tasks failed: %s", exc)
                self._log_error(f"Jellyfin tasks failed: {exc}")
                self._update_state(
                    state="error",
                    message="Jellyfin tasks failed",
                    last_error=str(exc),
                    progress=0,
                    active_file=None,
                )
                log_activity_error("jellyfin.run_failed", error=str(exc))
        except Exception as exc:
            LOGGER.exception("Jellyfin tasks failed: %s", exc)
            self._log_error(f"Jellyfin tasks failed: {exc}")
            self._update_state(
                state="error",
                message="Jellyfin tasks failed",
                last_error=str(exc),
                progress=0,
                active_file=None,
            )
            log_activity_error("jellyfin.run_failed", error=str(exc))
        finally:
            with self._lock:
                self._jellyfin_thread = None
                self._jellyfin_stop_event.clear()

    def _sync_directory(
        self,
        sftp: paramiko.SFTPClient,
        remote_path: str,
        local_path: Path,
        skip_folders: set[str],
        last_sync_cutoff: float,
    ) -> None:
        if self._stop_event.is_set():
            raise StopRequested()

        try:
            entries = sftp.listdir_attr(remote_path)
        except Exception as exc:
            self._log_error(f"Cannot list {remote_path}: {exc}")
            return

        for entry in entries:
            if self._stop_event.is_set():
                raise StopRequested()

            remote_item = f"{remote_path.rstrip('/')}/{entry.filename}"
            local_item = local_path / entry.filename

            if stat.S_ISDIR(entry.st_mode):
                if entry.filename.strip().lower() in skip_folders:
                    continue
                self._sync_directory(
                    sftp,
                    remote_item,
                    local_item,
                    skip_folders,
                    last_sync_cutoff,
                )
            else:
                if self._is_same_file(local_item, entry.st_size):
                    LOGGER.debug("Skipping %s; already present locally.", local_item)
                    continue
                if entry.st_mtime > last_sync_cutoff:
                    self._download_file(sftp, remote_item, local_item, entry.st_size)
                else:
                    LOGGER.debug(
                        "Skipping %s; unchanged since last sync (remote mtime=%s, cutoff=%s).",
                        remote_item,
                        entry.st_mtime,
                        last_sync_cutoff,
                    )

    def _download_file(
        self,
        sftp: paramiko.SFTPClient,
        remote_file: str,
        local_file: Path,
        size: int,
    ) -> None:
        local_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = local_file.with_suffix(local_file.suffix + ".partial")
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass
        filename = os.path.basename(remote_file)
        self._update_state(
            state="downloading",
            message="Downloading…",
            active_file=filename,
            target_path=str(local_file),
            progress=0,
        )

        last_update = time.time()
        last_transferred = 0

        def callback(transferred: int, total: int) -> None:
            nonlocal last_update, last_transferred
            if self._stop_event.is_set():
                raise StopRequested()
            percent = int((transferred / total) * 100) if total else 0
            now = time.time()
            elapsed = max(now - last_update, 1e-3)
            delta = max(transferred - last_transferred, 0)
            bytes_per_second = delta / elapsed if elapsed else 0
            last_update = now
            last_transferred = transferred
            self._update_state(
                progress=percent,
                download_speed=_format_speed(bytes_per_second),
            )

        buffer_size = 64 * 1024
        try:
            with sftp.open(remote_file, "rb") as remote_handle, open(temp_file, "wb") as local_handle:
                try:
                    remote_handle.prefetch()
                except Exception:
                    pass
                while True:
                    if self._stop_event.is_set():
                        raise StopRequested()
                    chunk = remote_handle.read(buffer_size)
                    if not chunk:
                        break
                    local_handle.write(chunk)
                    callback(local_handle.tell(), size)
            os.replace(temp_file, local_file)
            self._record_transfer(filename, size, str(local_file), "success")
            self._bump_stats(files=1, bytes=size)
        except StopRequested:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise
        except Exception as exc:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            self._record_transfer(
                filename,
                size,
                str(local_file),
                "failure",
                error_message=str(exc),
            )
            self._bump_stats(errors=1)
            self._log_error(f"{remote_file} - {exc}")
        finally:
            self._update_state(progress=0, download_speed=None, active_file=None, target_path=None)

    def _record_transfer(
        self,
        filename: str,
        size: int,
        target_path: str,
        status: Literal["in-progress", "success", "failure"],
        error_message: Optional[str] = None,
    ) -> None:
        record = FileTransfer(
            filename=filename,
            size=size,
            target_path=target_path,
            status=status,
            completed_at=datetime.utcnow() if status != "in-progress" else None,
            error_message=error_message,
        )
        with self._lock:
            self._recent_transfers.appendleft(record)
            self._state.recent_transfers = list(self._recent_transfers)
        if status in {"success", "failure"}:
            log_event(
                "transfer.recorded",
                filename=filename,
                target_path=target_path,
                size=size,
                status=status,
                error=error_message,
            )

    def _bump_stats(self, files: int = 0, bytes: int = 0, errors: int = 0) -> None:
        with self._lock:
            stats = self._state.stats
            stats.files_downloaded += files
            stats.bytes_downloaded += bytes
            stats.errors += errors
            self._state.stats = stats

    def _update_state(self, **updates) -> None:
        with self._lock:
            for key, value in updates.items():
                setattr(self._state, key, value)

    def _log_error(self, message: str) -> None:
        config_store.append_error(message)
        with self._lock:
            self._state.last_error = message
        log_activity_error("sync.error", message=message)

    def _is_same_file(self, local_file: Path, remote_size: int) -> bool:
        try:
            if not local_file.exists():
                return False
            local_size = local_file.stat().st_size
        except OSError:
            return False
        return local_size == remote_size

    def _store_active_connection(self, client: SSHClient, sftp: paramiko.SFTPClient) -> None:
        with self._connection_lock:
            self._ssh_client = client
            self._sftp_handle = sftp

    def _close_active_connection(self) -> None:
        with self._connection_lock:
            sftp = self._sftp_handle
            client = self._ssh_client
            self._sftp_handle = None
            self._ssh_client = None
        if sftp:
            try:
                sftp.close()
            except Exception:
                pass
        if client:
            try:
                client.close()
            except Exception:
                pass

    def set_next_sync_time(self, timestamp: Optional[float]) -> None:
        self._update_state(next_sync_time=timestamp)

    def _resolve_sync_cutoff(self, config: SftpConfig) -> float:
        manual = self._parse_manual_cutoff(config.start_after)
        if manual is not None:
            return manual
        return config_store.get_last_sync_time() or 0.0

    def _parse_manual_cutoff(self, value: str | None) -> float | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            LOGGER.warning("Invalid manual cutoff datetime provided: %s", value)
            return None
        if dt.tzinfo is None:
            local_tz = datetime.now().astimezone().tzinfo or timezone.utc
            dt = dt.replace(tzinfo=local_tz)
        return dt.timestamp()

    def _should_run_jellyfin_after_sync(self) -> bool:
        try:
            cfg = config_store.get_jellyfin_config()
        except Exception as exc:
            LOGGER.warning("Unable to read Jellyfin configuration: %s", exc)
            return False
        if not cfg.tested:
            return False
        return any(task.enabled for task in cfg.selected_tasks)

    def _handle_jellyfin_progress(
        self,
        task_name: str,
        task_progress: float,
        task_state: str,
        index: int,
        total: int,
    ) -> None:
        total = max(total, 1)
        overall = int((((index - 1) + (task_progress / 100.0)) / total) * 100)
        overall = max(0, min(100, overall))
        message = f"Jellyfin tasks ({index}/{total}) - {task_state}"
        self._update_state(
            state="jellyfin",
            message=message,
            active_file=task_name,
             target_path=f"{task_state} ({task_progress:.0f}%)",
            progress=overall,
            download_speed=None,
        )


def _format_speed(bytes_per_second: float) -> str:
    if bytes_per_second < 1024:
        return f"{bytes_per_second:.0f} B/s"
    if bytes_per_second < 1024**2:
        return f"{bytes_per_second / 1024:.2f} KB/s"
    return f"{bytes_per_second / (1024**2):.2f} MB/s"


sync_service = SyncService()
