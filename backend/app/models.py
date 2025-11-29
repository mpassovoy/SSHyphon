from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SftpConfig(BaseModel):
    host: str = Field("", description="Remote SFTP host name or IP")
    port: int = Field(22, description="SFTP port", ge=1, le=65535)
    username: str = Field("", description="SFTP username")
    password: str = Field("", description="Optional password, masked on reads")
    remote_root: str = Field("", description="Remote root directory to mirror")
    local_root: str = Field("", description="Local destination directory")
    skip_folders: list[str] = Field(default_factory=list, description="Folder names to ignore")
    sync_interval_minutes: int = Field(240, ge=5, le=24 * 60, description="Auto-sync cadence in minutes")
    auto_sync_enabled: bool = Field(False, description="Whether to run automatic sync cycles")
    start_after: str | None = Field(
        None,
        description="Optional ISO timestamp; only download files modified after this moment",
    )

    @field_validator("skip_folders", mode="before")
    @classmethod
    def _normalize_skip_list(cls, value: list[str] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            tokens = [part.strip() for part in value.split(",")]
        else:
            tokens = value
        return [token for token in (t.strip() for t in tokens or []) if token]


class ConfigResponse(SftpConfig):
    has_password: bool = Field(False, description="Indicates whether a password is stored securely")
    last_sync_time: Optional[float] = Field(None, description="Epoch timestamp of last successful sync")


class SyncStats(BaseModel):
    files_downloaded: int = 0
    bytes_downloaded: int = 0
    errors: int = 0


class FileTransfer(BaseModel):
    filename: str
    size: int
    target_path: str
    status: Literal["in-progress", "success", "failure"]
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class SyncStatus(BaseModel):
    state: Literal["idle", "connecting", "scanning", "downloading", "stopping", "error", "jellyfin"] = "idle"
    message: str = "Idle"
    active_file: Optional[str] = None
    target_path: Optional[str] = None
    progress: int = 0
    download_speed: Optional[str] = None
    stats: SyncStats = Field(default_factory=SyncStats)
    recent_transfers: list[FileTransfer] = Field(default_factory=list)
    last_error: Optional[str] = None
    last_sync_time: Optional[float] = None
    next_sync_time: Optional[float] = None


class JellyfinSelectedTask(BaseModel):
    key: str
    name: str
    enabled: bool = True
    order: int = 0
    legacy_id: Optional[str] = None


class JellyfinConfig(BaseModel):
    server_url: str = Field("", description="Base URL for Jellyfin / Emby")
    api_key: str = Field("", description="API key for Jellyfin; masked on reads")
    include_hidden_tasks: bool = Field(True, description="Whether to include hidden scheduled tasks")
    selected_tasks: list[JellyfinSelectedTask] = Field(
        default_factory=list, description="Ordered list of selected tasks to run"
    )
    tested: bool = Field(False, description="Indicates whether the connection was successfully tested")


class JellyfinConfigResponse(JellyfinConfig):
    has_api_key: bool = Field(False, description="Indicates whether a key is stored securely")


class JellyfinTask(BaseModel):
    name: str
    id: str
    key: str
    description: Optional[str] = None
    is_hidden: bool = False


class JellyfinTestRequest(BaseModel):
    server_url: str = Field("", description="Base URL to test")
    api_key: str = Field("", description="API key to test")
    include_hidden_tasks: bool = Field(True, description="Whether to include hidden tasks during test")
    persist: bool = Field(False, description="Persist the successful test result on the server")


class AuthRequest(BaseModel):
    username: str = Field("", description="Username for authentication")
    password: str = Field("", description="Password for authentication")
    remember_me: bool = Field(False, description="Extend session duration and remember the user")


class AuthResponse(BaseModel):
    token: str
    expires_at: float


class AuthStatus(BaseModel):
    configured: bool
    authenticated: bool
    session_expires_at: float | None = None
