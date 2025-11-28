# <img src="resources/icons/icon_256.png" alt="SSHyphon icon" width="32" height="32" style="vertical-align:middle;margin-right:0.35rem;" /> SSHyphon

SSHyphon is a Docker-native SFTP sync control surface with a FastAPI backend and React/Vite frontend—the name is a wink to “SSH hyphen” because it bridges secure shell workflows with clean separation between sync and UI. The web dashboard handles SFTP transfers, Jellyfin task orchestration, logging, and scheduling inside a single container.

![SSHyphon Web UI](docs/SSHyphon_main.png)

## Highlights
- **Unified dashboard** – status tiles, transfer history, activity/error logs, and performant controls under one SPA.
- **SFTP sync engine** – Paramiko-driven transfers with live stats, progress, and Jellyfin task hooks, all coordinated from the UI.
- **Docker-native deployment** – multi-stage image, single Uvicorn process on port `8000`, and persistent logs/configs in `/data`.
- **Jellyfin orchestration** – configure Jellyfin servers and tasks, trigger runs alongside sync jobs, and monitor task status.
- **Background scheduling** – optional auto-sync keeps your mirror up to date on a configurable interval.

## Getting Started
1. Build or pull the Docker image via `docker compose up --build` from the repo root (the provided `compose.yml` exposes port `8000` and mounts your sync/local data paths).
2. Mount your target folder into the container (for example, `./local-sync` → `/local-sync`) so downloaded files persist on the host.
3. Open `http://localhost:8000` in a browser, set the **Local Root** to the path inside the container (e.g., `/local-sync`), and supply your SFTP credentials + Remote Root.
4. Save the configuration, then run a sync or enable auto-sync. Logs and recent transfers appear instantly in the UI.

## UI Features
- **Config sections** – SSH credentials, Jellyfin setup, and task management each have dedicated tabs with help text.
- **Status tiles** – show the worker state, last/next sync, Jellyfin errors, and quick actions (Start/Stop sync).
- **Recent transfers** – responsive table with totals, timestamps, and inline filters.
- **Logs** – activity and error logs can be refreshed, cleared, or downloaded with a single click (timestamped filenames).

## Troubleshooting
| Issue | Fix |
| --- | --- |
| Docker container cannot write to the local root | Ensure the host directory is mounted and the container user has write access (running as root is the easiest way). |
| “Missing credentials” when starting a sync | Fill every required form field and save the password once—saved secrets display as `********`. |
| Auto-sync is not firing | Confirm the toggle is on, the interval is ≥ 5 minutes, and the worker is idle. Saving a new config restarts the scheduler immediately. |
| Frontend returns 404 | The API serves the built SPA from `/app/frontend_dist`. Rebuild the frontend (`npm run build`) or rerun `docker compose build` whenever UI assets change. |

## Warnings & Legal
- The container can only write to directories you explicitly mount; verify your volume mappings before syncing.
- Secrets are stored in JSON under `/data`. For sensitive deployments, use an encrypted volume or external secret store.
- Do not sync material you are not authorized to distribute. You are solely responsible for compliance with copyright, licensing, and service terms.

