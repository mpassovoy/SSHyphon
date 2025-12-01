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

[<img src="../SSHyphon_main.png" alt="SSHyphon Main Window" width="600" />](../SSHyphon_main.png)

## First login and config save
1. Open `http://localhost:8000` and log in (no default credentials required).
2. Navigate to the **Settings** tab and fill in:
   - **Local Root**: the container path you mounted for downloads (e.g., `/local-sync`).
   - **Remote Root** and SFTP credentials.
   - Any optional Jellyfin server info if you plan to trigger tasks.
3. Click **Save Settings**. Secrets are persisted inside `/data` and shown as `********` afterward.
4. Run a manual sync or enable **Auto-sync** to start scheduled mirroring.

[<img src="../sync_settings.png" alt="Sync Settings" width="600" />](../sync_settings.png)

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

## Deploying on TrueNAS with a custom YAML
If you use the TrueNAS `docker-compose` UI or a custom YAML, you can mirror the repo’s `compose.yml` while pointing to your storage pools:

1. In TrueNAS, go to Apps>Discover Apps>Install via YAML.

[<img src="../truenas_yaml.png" alt="TrueNAS YAML Install" width="800" />](../truenas_yaml.png)

2. Enter the YAML config for SSHyhon:
   ```yaml
   services:
     sshyphon:
       image: https://ghcr.io/mpassovoy/sshyphon:latest # or update with version, https://ghcr.io/mpassovoy/sshyphon:v0.0.X
       container_name: sshyphon
       ports:
         - "8000:8000"
       volumes:
         - /mnt/tank/apps/sshyphon/data:/data
         - /mnt/tank/media/local-sync:/local-sync  # update to the root folder to expose to SSHyphon
       restart: unless-stopped
   ```
3. Hit Save.

[<img src="../truenas_yaml_config.png" alt="TrueNAS YAML Install window" width="600" />](../truenas_yaml_config.png)

4. After the container starts, open `http://<truenas-host>:8000`, set **Local Root** to `/local-sync`, and save settings so secrets persist under `/data`.
