# Logs, backups, and recovery

Operational tips for maintaining SSHyphon data and recovering from misconfiguration.

## Where data lives
- **Configs & secrets**: `/data` volume holds settings JSON files and encrypted credentials.
- **Logs**: `/data/logs` plus downloadable archives via the UI **Logs** tab.
- **Downloaded files**: whatever host path you map to `/local-sync`.

## Export logs from the UI
1. Open the **Logs** tab.
2. Use **Refresh** to pull the latest entries.
3. Click **Download Logs** to save a timestamped archive for support or auditing.

![Log controls](../SSHyphon_main.png)

## Back up important files
- Back up the entire `/data` volume to preserve configs, secrets, and history.
- Optionally back up the `/local-sync` mount if you want a copy of mirrored files elsewhere.
- For GitOps-style environments, keep `compose.yml` and any override files under version control alongside your infrastructure code.

## Reset the app safely
If you need to start fresh:
1. Stop the container.
2. Move or delete the `/data` volume contents (this wipes saved credentials and schedules).
3. Start the container again and re-enter settings in the UI.

## Recover access if you are locked out
If you cannot log in (lost username/password):
1. Stop the container to avoid writing while you edit files (`docker compose stop sshyphon`).
2. On the host, delete the auth file in your data mount (default `./data/auth.json` when using the provided `compose.yml`).
3. Restart the container (`docker compose up -d sshyphon`). The app will behave as unconfigured authentication—open the UI and set a new username and password on the login/setup screen.
4. If you also want to clear saved SFTP secrets at the same time, delete `./data/secrets.json` before restarting.

## Container health checks
- Confirm the web UI responds on the published port (default `8000`).
- Verify the worker shows **Idle** when not running a job and updates after each sync.
- Check container logs with `docker compose logs -f sshyphon` for runtime errors.
