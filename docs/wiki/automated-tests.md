# Automated tests

This page lists the automated tests that ship with SSHyphon so you can quickly find the coverage area for backend APIs and the frontend UI.

## Backend tests
| File | What it covers |
| --- | --- |
| `backend/tests/test_activity_log.py` | Serializing activity payloads safely, reading the activity log without crashing on missing files, and clearing the log file. |
| `backend/tests/test_auto_sync.py` | Auto-sync controller behavior: arming timers, restart handling, scheduling, retry and cancellation rules, and logging for in-progress or credential errors. |
| `backend/tests/test_auth_sessions.py` | Auth setup and login flows, remember-me TTLs, logging success/failure events, session eviction, logout, and token verification middleware. |
| `backend/tests/test_config_store.py` | Loading/saving auth records, validation of SFTP configuration, migration behavior, and masking/unmasking stored passwords. |
| `backend/tests/test_jellyfin_config.py` | Validation and merging of Jellyfin config values, including auth token handling and password masking. |
| `backend/tests/test_jellyfin_service.py` | Jellyfin service flows for status, login, configuration, job control, and error handling. |
| `backend/tests/test_main.py` | FastAPI startup configuration, health endpoint response, and serving of the frontend app. |
| `backend/tests/test_sync_service.py` | Sync service lifecycle: status transitions, start/stop hooks, next sync time tracking, and persistence of sync metadata. |
| `backend/tests/test_versioning.py` | Version metadata reporting and update-availability logic. |

## Frontend tests
| File | What it covers |
| --- | --- |
| `frontend/src/__tests__/ActivityLogView.test.tsx` | Rendering the activity log panel, clearing logs, and surfacing errors. |
| `frontend/src/__tests__/App.test.tsx` | App bootstrap flow, dashboard data loads, toast notifications, and login/logout wiring. |
| `frontend/src/__tests__/AuthLogin.test.tsx` | Login form validation, remember-me behavior, and error handling. |
| `frontend/src/__tests__/ConfigForm.test.tsx` | Editing configuration fields, validation errors, and saving updates to the backend. |
| `frontend/src/__tests__/JellyfinSetup.test.tsx` | Jellyfin connection form, login/save actions, and masked password handling. |
| `frontend/src/__tests__/JellyfinTasksManager.test.tsx` | Scheduling and controlling Jellyfin tasks plus how progress/errors are displayed. |
| `frontend/src/__tests__/StatusPanel.test.tsx` | Sync status rendering, progress reporting, start/stop buttons, and error toasts. |
| `frontend/src/__tests__/TransfersTable.test.tsx` | Listing recent transfers, empty-state messaging, and formatting of transfer metadata. |
| `frontend/src/__tests__/VersionBanner.test.tsx` | Showing current vs. latest version info and update-available banners. |
