# API Reference

This page summarizes the HTTP APIs exposed by the SSHyphon backend, including each route's purpose, HTTP method, and the expected request and response payloads. All endpoints are rooted at `/api` and return JSON unless noted otherwise.

## Authentication
Most endpoints require authentication. The `Authorization: Bearer <token>` header is required for protected routes after a successful login or setup.

### `GET /api/health`
- **Purpose:** Lightweight liveness probe.
- **Request:** No body.
- **Response:** `{ "status": "ok" }`.

### `GET /api/version`
- **Purpose:** Read application version metadata for the UI footer or diagnostics.
- **Request:** No body.
- **Response:** Version payload including semantic version and build hash.

### `GET /api/auth/status`
- **Purpose:** Determine whether authentication is configured and whether the requester is signed in.
- **Request:** No body; session token is optional.
- **Response:** `AuthStatus` object with `configured`, `authenticated`, and optional `session_expires_at`.

### `POST /api/auth/setup`
- **Purpose:** Create the initial username/password when auth is not yet configured.
- **Request:** `AuthRequest` body `{ username, password, remember_me }`.
- **Response:** `AuthResponse` `{ token, expires_at }` for immediate use.

### `POST /api/auth/login`
- **Purpose:** Log into an existing instance.
- **Request:** `AuthRequest` body `{ username, password, remember_me }`.
- **Response:** `AuthResponse` `{ token, expires_at }`.

### `POST /api/auth/logout`
- **Purpose:** Invalidate the active session.
- **Request:** No body; requires valid bearer token.
- **Response:** `{ "status": "ok" }`.

## SFTP Configuration
### `GET /api/config`
- **Purpose:** Read stored SFTP configuration for the sync service.
- **Request:** Optional query `reveal` to unmask secrets; requires auth.
- **Response:** `ConfigResponse` containing the SFTP fields plus `has_password` and `last_sync_time`.

### `PUT /api/config`
- **Purpose:** Save SFTP configuration and refresh the auto-sync controller.
- **Request:** `SftpConfig` body with fields such as `host`, `port`, `username`, `password`, `remote_root`, `local_root`, `skip_folders`, `sync_interval_minutes`, `auto_sync_enabled`, and optional `start_after` ISO timestamp.
- **Response:** Same shape as `ConfigResponse` with masked secrets.

## Sync Control
### `GET /api/status`
- **Purpose:** Inspect current sync state, recent transfers, and timing of the next run.
- **Request:** No body; requires auth.
- **Response:** `SyncStatus` object including `state`, `message`, `progress`, `recent_transfers`, `last_sync_time`, and `next_sync_time`.

### `POST /api/sync/start`
- **Purpose:** Start a manual sync immediately and schedule the next automatic cycle.
- **Request:** No body; requires auth. Errors include 400 when credentials are missing and 409 when a sync is already in progress.
- **Response:** Current `SyncStatus` after the start is queued.

### `POST /api/sync/stop`
- **Purpose:** Cancel the current sync and clear the next scheduled run.
- **Request:** No body; requires auth.
- **Response:** Final `SyncStatus` after cancellation.

## Activity & Error Logs
### `GET /api/errors`
- **Purpose:** Fetch recent error entries.
- **Request:** Optional query `limit` (default 200); requires auth.
- **Response:** `{ "errors": ["..."] }` string array.

### `POST /api/errors/clear`
- **Purpose:** Truncate the error log file.
- **Request:** No body; requires auth.
- **Response:** `{ "status": "ok" }`.

### `GET /api/errors/download`
- **Purpose:** Download the raw error log.
- **Request:** No body; requires auth.
- **Response:** Plain-text file attachment named `errors-<timestamp>.log`.

### `GET /api/activity/log`
- **Purpose:** Read recent activity log entries.
- **Request:** Optional query `limit` (default 1000); requires auth.
- **Response:** `{ "entries": [ { event details... } ] }`.

### `POST /api/activity/clear`
- **Purpose:** Remove all activity entries.
- **Request:** No body; requires auth.
- **Response:** `{ "status": "ok" }`.

### `GET /api/activity/download`
- **Purpose:** Download the activity log as text.
- **Request:** No body; requires auth.
- **Response:** Plain-text file attachment named `activity-<timestamp>.log`.

## Jellyfin Integration
### `GET /api/jellyfin/config`
- **Purpose:** Read stored Jellyfin/Emby connection settings.
- **Request:** Optional query `reveal` to unmask the API key; requires auth.
- **Response:** `JellyfinConfigResponse` with `server_url`, `include_hidden_tasks`, `selected_tasks`, `tested`, and `has_api_key`.

### `PUT /api/jellyfin/config`
- **Purpose:** Save Jellyfin settings.
- **Request:** `JellyfinConfig` body with `server_url`, `api_key`, `include_hidden_tasks`, `selected_tasks` (array of `{ key, name, enabled, order, legacy_id }`), and `tested` flag.
- **Response:** Stored `JellyfinConfigResponse` with secrets masked.

### `POST /api/jellyfin/test`
- **Purpose:** Test connectivity to Jellyfin using provided or saved credentials.
- **Request:** Optional `JellyfinTestRequest` body `{ server_url, api_key, include_hidden_tasks, persist }`; requires auth.
- **Response:** `{ "status": "ok" }` on success, 400 with details on failure.

### `GET /api/jellyfin/tasks`
- **Purpose:** List available Jellyfin scheduled tasks for selection.
- **Request:** No body; requires auth.
- **Response:** Array of `JellyfinTask` objects `{ name, id, key, description, is_hidden }`.

### `POST /api/jellyfin/tasks/run`
- **Purpose:** Trigger the selected Jellyfin tasks immediately.
- **Request:** No body; requires auth. Returns 409 when another sync is running.
- **Response:** `SyncStatus` representing the Jellyfin task execution state.

## File Serving
### `GET /`
- **Purpose:** Serve the built frontend (when available). This is excluded from the OpenAPI schema and not namespaced under `/api`.
- **Request/Response:** Serves `index.html` and frontend assets; not a JSON API.

