import { useEffect, useState } from "react";
import type { JellyfinConfigResponse } from "../api/types";
import { fetchJellyfinConfig, testJellyfinConnection, updateJellyfinConfig } from "../api/service";
import toast from "react-hot-toast";

type Props = {
  onClose: () => void;
  onManageTasks: () => void;
};

export function JellyfinSetup({ onClose, onManageTasks }: Props) {
  const [config, setConfig] = useState<JellyfinConfigResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [apiKeyVisible, setApiKeyVisible] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [resolvedApiKey, setResolvedApiKey] = useState("");
  const [isDirty, setIsDirty] = useState(false);
  const MASK = "********";

  const hasServerUrl = Boolean(config?.server_url?.trim());
  const hasApiKey = Boolean(
    apiKeyInput || resolvedApiKey || (config?.has_api_key && apiKeyInput === MASK)
  );
  const manageTasksDisabled =
    !hasServerUrl || !hasApiKey || isDirty || !config?.tested || saving || testing;
  const manageTasksTooltip = !hasServerUrl || !hasApiKey
    ? "Jellyfin Server and API Key are required before Tasks are available."
    : isDirty
      ? "Save settings before managing tasks."
      : !config?.tested
        ? "Test and validate the connection before managing tasks."
        : saving
          ? "Wait for settings to finish saving."
          : testing
            ? "Wait for the connection test to finish."
            : "";

  useEffect(() => {
    const load = async () => {
      try {
        const cfg = await fetchJellyfinConfig();
        setConfig(cfg);
        setApiKeyInput(cfg.has_api_key ? MASK : cfg.api_key || "");
        setIsDirty(false);
      } catch (error) {
        console.error(error);
        toast.error("Unable to load Jellyfin configuration");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleFieldChange = (field: keyof JellyfinConfigResponse, value: string | boolean) => {
    if (!config) return;
    const next = { ...config, [field]: value } as JellyfinConfigResponse;
    if (field === "server_url" || field === "api_key") {
      next.tested = false;
      setIsDirty(true);
    }
    setConfig(next);
    if (field === "api_key") {
      setApiKeyInput(String(value));
      setResolvedApiKey("");
    }
  };

  const ensureActualApiKey = async (): Promise<string> => {
    if (!config) return "";
    if (apiKeyInput && apiKeyInput !== MASK) {
      setResolvedApiKey(apiKeyInput);
      return apiKeyInput;
    }
    if (resolvedApiKey) {
      return resolvedApiKey;
    }
    if (config.has_api_key) {
      try {
        const revealed = await fetchJellyfinConfig({ reveal: true });
        setResolvedApiKey(revealed.api_key);
        if (apiKeyVisible) {
          setApiKeyInput(revealed.api_key);
        }
        return revealed.api_key;
      } catch (error) {
        console.error(error);
        toast.error("Unable to reveal stored API key");
        throw error;
      }
    }
    return "";
  };

  const toggleApiKeyVisibility = async () => {
    if (!config) return;
    if (!apiKeyVisible) {
      const actual = await ensureActualApiKey();
      if (actual) {
        setApiKeyInput(actual);
      }
    } else {
      setApiKeyInput(config.has_api_key ? MASK : "");
    }
    setApiKeyVisible((prev) => !prev);
  };

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!config) return;
    setSaving(true);
    try {
      const keyToSave = await ensureActualApiKey();
      const payload = {
        ...config,
        api_key: keyToSave,
        selected_tasks: config.selected_tasks
      };
      const updated = await updateJellyfinConfig(payload);
      setConfig(updated);
      setApiKeyInput(updated.has_api_key ? MASK : updated.api_key || "");
      setResolvedApiKey(updated.has_api_key ? keyToSave : "");
      setIsDirty(false);
      toast.success("Jellyfin settings saved");
      onClose();
    } catch (error) {
      console.error(error);
      toast.error("Unable to save Jellyfin settings");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!config) return;
    setTesting(true);
    try {
      const apiKeyValue = await ensureActualApiKey();
      await testJellyfinConnection({
        server_url: config.server_url,
        api_key: apiKeyValue,
        persist: !isDirty
      });
      toast.success("Jellyfin connection OK");
      setConfig((prev) => (prev ? { ...prev, tested: true } : prev));
    } catch (error: any) {
      console.error(error);
      toast.error(error?.response?.data?.detail ?? "Jellyfin test failed");
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="config-view">
        <p className="muted">Loading Jellyfin configuration…</p>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="config-view">
        <p className="muted">Jellyfin configuration could not be loaded.</p>
      </div>
    );
  }

  return (
    <div className="config-view">
      <div className="settings-tab-actions">
        <button className="primary-btn" type="button" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>

      <form onSubmit={handleSave} className="card" style={{ marginBottom: "1.5rem" }}>
        <h2>Connection</h2>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="jf-url">Server URL</label>
            <input
              id="jf-url"
              value={config.server_url}
              onChange={(e) => handleFieldChange("server_url", e.target.value)}
              placeholder="http://jellyfin.local:8096"
              required
            />
          </div>
          <div className="form-field">
            <label htmlFor="jf-key">API Key</label>
            <div className="password-field">
              <input
                id="jf-key"
                type={apiKeyVisible ? "text" : "password"}
                value={apiKeyInput}
                onChange={(e) => handleFieldChange("api_key", e.target.value)}
                placeholder={config.has_api_key ? MASK : "Paste API key"}
              />
              {config.has_api_key && (
                <button type="button" className="password-toggle" onClick={toggleApiKeyVisibility}>
                  {apiKeyVisible ? "Hide" : "Show"}
                </button>
              )}
            </div>
          </div>
        </div>
        <div className="flex-row" style={{ justifyContent: "space-between", alignItems: "center", marginTop: "1rem" }}>
          <span className="muted">Connection status: {config.tested ? "Tested" : "Not tested yet"}</span>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button className="primary-btn" type="button" onClick={handleTest} disabled={testing}>
              {testing ? "Testing…" : "Test connection"}
            </button>
            <button
              className="secondary-btn"
              type="button"
              onClick={onManageTasks}
              disabled={manageTasksDisabled}
              title={manageTasksTooltip || undefined}
            >
              Manage tasks
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
