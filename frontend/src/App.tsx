import { useCallback, useEffect, useState } from "react";
import toast, { Toaster } from "react-hot-toast";
import { fetchConfig, fetchErrors, fetchStatus, fetchVersionInfo, startSync, stopSync, updateConfig } from "./api/service";
import type { ConfigResponse, SftpConfig, SyncStatus, VersionInfo } from "./api/types";
import { ConfigForm } from "./components/ConfigForm";
import { ErrorLog } from "./components/ErrorLog";
import { JellyfinSetup } from "./components/JellyfinSetup";
import { JellyfinTasksManager } from "./components/JellyfinTasksManager";
import { ActivityLogView } from "./components/ActivityLogView";
import { StatusPanel } from "./components/StatusPanel";
import { TransfersTable } from "./components/TransfersTable";

export default function App() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [savingConfig, setSavingConfig] = useState(false);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [viewMode, setViewMode] = useState<"dashboard" | "config" | "jellyfin" | "jellyfinTasks" | "logs">("dashboard");
  const [configFormValid, setConfigFormValid] = useState(false);
  const [logTab, setLogTab] = useState<"activity" | "errors">("activity");
  const [versionInfo, setVersionInfo] = useState<VersionInfo | null>(null);
  const buildVersion = import.meta.env.VITE_APP_VERSION ?? "0.0.0";
  const updateAvailable = Boolean(versionInfo?.update_available && versionInfo.latest_version);
  const latestVersion = versionInfo?.latest_version;
  const canStart =
    !!config &&
    !!config.host &&
    !!config.username &&
    !!config.remote_root &&
    !!config.local_root &&
    (!!config.password || config.has_password);

  const loadConfig = useCallback(async () => {
    try {
      const data = await fetchConfig();
      setConfig(data);
    } catch (error) {
      console.error(error);
      toast.error("Unable to load configuration");
    }
  }, []);

  const loadStatus = useCallback(async () => {
    try {
      const data = await fetchStatus();
      setStatus(data);
    } catch (error) {
      console.error(error);
    }
  }, []);

  const loadErrors = useCallback(async () => {
    try {
      const data = await fetchErrors();
      setErrors(data);
    } catch (error) {
      console.error(error);
    }
  }, []);

  const handleRevealPassword = useCallback(async () => {
    try {
      const data = await fetchConfig({ reveal: true });
      return data.password;
    } catch (error) {
      console.error(error);
      toast.error("Unable to reveal password");
      return "";
    }
  }, []);

  useEffect(() => {
    loadConfig();
    loadStatus();
    loadErrors();
  }, [loadConfig, loadStatus, loadErrors]);

  const loadVersionInfo = useCallback(async () => {
    try {
      const info = await fetchVersionInfo();
      setVersionInfo(info);
    } catch (error) {
      console.error(error);
    }
  }, []);

  useEffect(() => {
    loadVersionInfo();
  }, [loadVersionInfo]);

  useEffect(() => {
    const intervalMs = status?.state === "jellyfin" ? 1000 : 3000;
    const interval = setInterval(loadStatus, intervalMs);
    return () => clearInterval(interval);
  }, [loadStatus, status?.state]);

  useEffect(() => {
    const interval = setInterval(loadErrors, 10000);
    return () => clearInterval(interval);
  }, [loadErrors]);

  const handleSave = async (payload: SftpConfig) => {
    setSavingConfig(true);
    try {
      const updated = await updateConfig(payload);
      setConfig(updated);
      toast.success("Settings saved");
    } catch (error) {
      console.error(error);
      toast.error("Unable to save settings");
    } finally {
      setSavingConfig(false);
    }
  };

  const handleStart = async () => {
    setStarting(true);
    try {
      const next = await startSync();
      setStatus(next);
      toast.success("Sync started");
    } catch (error: any) {
      const message = error?.response?.data?.detail ?? "Unable to start sync";
      toast.error(message);
    } finally {
      setStarting(false);
    }
  };

  const handleStop = async () => {
    setStopping(true);
    try {
      const next = await stopSync();
      setStatus(next);
      toast("Stop requested");
    } catch (error: any) {
      const message = error?.response?.data?.detail ?? "Unable to stop sync";
      toast.error(message);
    } finally {
      setStopping(false);
    }
  };

  const handleOpenConfig = () => setViewMode("config");
  const handleCloseConfig = () => setViewMode("dashboard");
  const handleOpenJellyfin = () => setViewMode("jellyfin");
  const handleOpenLogs = (tab: "activity" | "errors" = "activity") => {
    setLogTab(tab);
    setViewMode("logs");
  };
  const handleJellyfinTasksStart = (next?: SyncStatus) => {
    if (next) {
      setStatus(next);
    }
    setViewMode("dashboard");
  };

  return (
    <>
      <Toaster position="bottom-right" />
      {viewMode === "dashboard" ? (
        <div className="app-shell">
          <header className="app-header">
            <div className="logo-with-icon">
              <img src="/icons/icon_256.png" alt="SSHyphon icon" className="header-icon" />
              <div className="header-title">
                <h1>SSHyphon</h1>
                <div
                  className="header-version"
                  aria-label={`Build version ${buildVersion}`}
                >
                  <span className="header-version-text">v{buildVersion}</span>
                  {updateAvailable && (
                    <span
                      className="header-version-icon"
                      title={`Update available: ${latestVersion}`}
                    >
                      <svg viewBox="0 0 16 16" role="img" focusable="false">
                        <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.2" />
                        <path d="M8.5 4.5 8.5 9.5M5 6.5 8.5 3 12 6.5" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="top-action-bar button-group">
              <button className="primary-btn" onClick={handleOpenConfig}>
                Sync Settings
              </button>
              <button className="secondary-btn" onClick={handleOpenJellyfin}>
                Jellyfin Setup
              </button>
              <button className="secondary-btn" onClick={() => handleOpenLogs()}>
                Logs
              </button>
            </div>
          </header>
          <div className="dashboard-stack">
            <StatusPanel
              status={status}
              onStart={handleStart}
              onStop={handleStop}
              starting={starting}
              stopping={stopping}
              canStart={canStart}
              errorCount={errors.length}
              onOpenErrorLog={() => handleOpenLogs("errors")}
            />
            <TransfersTable transfers={status?.recent_transfers ?? []} stats={status?.stats ?? { files_downloaded: 0, bytes_downloaded: 0, errors: 0 }} />
          </div>
        </div>
      ) : viewMode === "config" ? (
        <div className="config-view">
          <div className="config-header">
            <h1>Sync Settings</h1>
            <div className="flex-row button-group">
              <button className="secondary-btn" type="button" onClick={handleCloseConfig}>
                Cancel
              </button>
              <button
                className="primary-btn"
                type="submit"
                form="sync-settings-form"
                disabled={!configFormValid || savingConfig}
              >
                {savingConfig ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
          <ConfigForm
            config={config}
            onSave={async (payload) => {
              await handleSave(payload);
              handleCloseConfig();
            }}
            onRevealPassword={handleRevealPassword}
            formId="sync-settings-form"
            onValidityChange={setConfigFormValid}
          />
        </div>
      ) : viewMode === "jellyfin" ? (
        <JellyfinSetup
          onClose={() => setViewMode("dashboard")}
          onManageTasks={() => setViewMode("jellyfinTasks")}
        />
      ) : viewMode === "logs" ? (
        <ActivityLogView initialTab={logTab} onClose={() => setViewMode("dashboard")} />
      ) : (
        <JellyfinTasksManager
          onClose={() => setViewMode("jellyfin")}
          onLaunchTasks={handleJellyfinTasksStart}
        />
      )}
    </>
  );
}
