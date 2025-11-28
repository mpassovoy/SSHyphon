import { useEffect, useMemo, useState } from "react";
import type { ConfigResponse, SftpConfig } from "../api/types";

const PASSWORD_MASK = "********";

const emptyConfig: SftpConfig = {
  host: "",
  port: 22,
  username: "",
  password: "",
  remote_root: "",
  local_root: "",
  skip_folders: [],
  sync_interval_minutes: 240,
  auto_sync_enabled: false,
  start_after: null
};

type Props = {
  config: ConfigResponse | null;
  onSave: (payload: SftpConfig) => Promise<void>;
  onRevealPassword?: () => Promise<string>;
  formId?: string;
  onValidityChange?: (isValid: boolean) => void;
};

export function ConfigForm({
  config,
  onSave,
  onRevealPassword,
  formId = "sync-settings-form",
  onValidityChange
}: Props) {
  const [form, setForm] = useState<SftpConfig>(emptyConfig);
  const [skipInput, setSkipInput] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [revealingPassword, setRevealingPassword] = useState(false);

  useEffect(() => {
    if (!config) return;
    const { has_password: _ignored, last_sync_time: _lastSync, ...rest } = config;
    setForm({ ...emptyConfig, ...rest });
    setSkipInput(config.skip_folders.join(", "));
  }, [config]);

  const isValid = useMemo(() => {
    if (!form.host || !form.username || !form.remote_root || !form.local_root) {
      return false;
    }
    return true;
  }, [form]);

  const handleChange = (field: keyof SftpConfig, value: string | number | boolean | null) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const payload: SftpConfig = {
      ...form,
      skip_folders: skipInput
        .split(",")
        .map((token) => token.trim())
        .filter(Boolean)
    };
    await onSave(payload);
  };

  const passwordIsMasked = form.password === PASSWORD_MASK;

  const handleTogglePassword = async () => {
    if (!showPassword && config?.has_password && passwordIsMasked && onRevealPassword) {
      setRevealingPassword(true);
      try {
        const revealed = await onRevealPassword();
        setForm((prev) => ({ ...prev, password: revealed || "" }));
      } catch (error) {
        console.error(error);
      } finally {
        setRevealingPassword(false);
      }
    }
    setShowPassword((prev) => !prev);
  };

  useEffect(() => {
    onValidityChange?.(isValid);
  }, [isValid, onValidityChange]);

  return (
    <form id={formId} className="card" onSubmit={handleSubmit}>
      <div className="config-form-header">
        <h2>Edit Settings</h2>
        <label
          className="auto-sync-toggle"
          title="When enabled, the sync starts immediately on restart and keeps running every interval without manually clicking the Start button."
        >
          <input
            type="checkbox"
            checked={form.auto_sync_enabled}
            onChange={(e) => handleChange("auto_sync_enabled", e.target.checked)}
            aria-label="Enable automatic sync"
          />
          <span className="toggle-track" aria-hidden>
            <span className="toggle-ball" />
          </span>
          <span className="toggle-label">Auto-Sync</span>
        </label>
      </div>
      <div className="form-grid two-column">
        <div className="form-field">
          <label htmlFor="host">SFTP Host</label>
          <input
            id="host"
            value={form.host}
            onChange={(e) => handleChange("host", e.target.value)}
            placeholder="sftp.example.com"
            required
          />
        </div>
        <input type="hidden" value={form.port || 22} />
        <div className="form-field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            value={form.username}
            onChange={(e) => handleChange("username", e.target.value)}
            placeholder="remote-user"
            required
          />
        </div>
        <div className="form-field">
          <label htmlFor="password">Password</label>
          <div className="password-field">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              value={form.password}
              onChange={(e) => handleChange("password", e.target.value)}
              placeholder={config?.has_password ? PASSWORD_MASK : "••••••"}
            />
            <button
              type="button"
              className="password-toggle"
              onClick={handleTogglePassword}
              disabled={revealingPassword}
            >
              {revealingPassword ? "Loading…" : showPassword ? "Hide" : "Show"}
            </button>
          </div>
        </div>
        <div className="form-field">
          <label htmlFor="remoteRoot">Remote Root</label>
          <input
            id="remoteRoot"
            value={form.remote_root}
            onChange={(e) => handleChange("remote_root", e.target.value)}
            placeholder="/remote/data"
            required
          />
        </div>
        <div className="form-field">
          <label htmlFor="localRoot">Local Root (container path)</label>
          <input
            id="localRoot"
            value={form.local_root}
            onChange={(e) => handleChange("local_root", e.target.value)}
            placeholder="/data/ingest"
            required
          />
        </div>
        <div className="form-field">
          <label htmlFor="skipFolders">Skip Folders</label>
          <input
            id="skipFolders"
            value={skipInput}
            onChange={(e) => setSkipInput(e.target.value)}
            placeholder='cache, "Raw Footage"'
          />
        </div>
        <div className="form-field">
          <label htmlFor="startAfter">Only download files modified after</label>
          <input
            id="startAfter"
            type="datetime-local"
            value={form.start_after ?? ""}
            onChange={(e) => handleChange("start_after", e.target.value || null)}
          />
          <small className="muted">Leave blank to download everything.</small>
        </div>
        <div className="form-field">
          <label htmlFor="interval">Sync Interval (minutes)</label>
          <input
            id="interval"
            type="number"
            min={5}
            max={1440}
            value={form.sync_interval_minutes}
            onChange={(e) => handleChange("sync_interval_minutes", Number(e.target.value))}
          />
        </div>
      </div>
      <br/>
      <span className="muted">
        <center>SSHyphon stores credentials securely and never exposes passwords over the API.</center>
      </span>
    </form>
  );
}
