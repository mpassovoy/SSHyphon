# Getting started

A minimal setup to run SSHyphon locally or on a home server using Docker. The goal is to get the UI reachable on port `8000`, with persistent storage for configs and synced files.

## Prerequisites
- Docker Engine with Compose plugin.
- Host directories for persistent data (examples assume the repo root).

## Quick start with `docker compose`
1. From the repository root, build and launch the stack:
   ```bash
   docker compose up --build
   ```
2. The container publishes the UI/API on `http://localhost:8000`.
3. Default mounts mirror the provided `compose.yml`:
   - `./data` → `/data` for configs, secrets, and logs.
   - `./local-sync` → `/local-sync` for downloaded files.
4. Adjust the host paths in `compose.yml` if you need different storage locations.

![Compose-ready dashboard](../SSHyphon_main.png)

## First login and config save
1. Open `http://localhost:8000` and log in (no default credentials required).
2. Navigate to the **Settings** tab and fill in:
   - **Local Root**: the container path you mounted for downloads (e.g., `/local-sync`).
   - **Remote Root** and SFTP credentials.
   - Any optional Jellyfin server info if you plan to trigger tasks.
3. Click **Save Settings**. Secrets are persisted inside `/data` and shown as `********` afterward.
4. Run a manual sync or enable **Auto-sync** to start scheduled mirroring.

![Settings form](../sync_settings.png)

## Building without Compose
If you prefer plain Docker commands:
```bash
docker build -t sshyphon:latest .
docker run -p 8000:8000 \
  -v $(pwd)/data:/data \
  -v $(pwd)/local-sync:/local-sync \
  sshyphon:latest
```
This mirrors the Compose defaults while letting you change the mount points to match your environment.
