import { useCallback, useEffect, useState } from "react";
import toast, { Toaster } from "react-hot-toast";
import {
  fetchAuthStatus,
  fetchConfig,
  fetchErrors,
  fetchStatus,
  fetchVersionInfo,
  logout as logoutRequest,
  startSync,
  stopSync,
  updateConfig
} from "./api/service";
import type { AuthResponse, ConfigResponse, SftpConfig, SyncStatus, VersionInfo } from "./api/types";
import { ConfigForm } from "./components/ConfigForm";
import { ErrorLog } from "./components/ErrorLog";
import { JellyfinSetup } from "./components/JellyfinSetup";
import { JellyfinTasksManager } from "./components/JellyfinTasksManager";
import { ActivityLogView } from "./components/ActivityLogView";
import { StatusPanel } from "./components/StatusPanel";
import { TransfersTable } from "./components/TransfersTable";
import { AuthLogin } from "./components/AuthLogin";
import { AuthSetup } from "./components/AuthSetup";
import { clearStoredSession, getStoredSession, persistSession } from "./utils/auth";
import { formatBuildVersion } from "./utils/version";

const SETTINGS_TABS: { id: "sync" | "jellyfin" | "logs"; label: string }[] = [
  { id: "sync", label: "Sync Settings" },
  { id: "jellyfin", label: "Jellyfin Setup" },
  { id: "logs", label: "Logs" }
];

function SiteFooter() {
  return (
    <footer className="site-footer">
      <a href="https://github.com/mpassovoy/SSHyphon" target="_blank" rel="noreferrer">
        View SSHyphon on GitHub
      </a>
    </footer>
  );
}

export default function App() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [savingConfig, setSavingConfig] = useState(false);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [viewMode, setViewMode] = useState<
    "dashboard" | "settings" | "jellyfinTasks"
  >("dashboard");
  const [settingsTab, setSettingsTab] = useState<"sync" | "jellyfin" | "logs">("sync");
  const [configFormValid, setConfigFormValid] = useState(false);
  const [logTab, setLogTab] = useState<"activity" | "errors">("activity");
  const [versionInfo, setVersionInfo] = useState<VersionInfo | null>(null);
  const [authConfigured, setAuthConfigured] = useState<boolean | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const buildVersion = import.meta.env.VITE_APP_VERSION ?? "0.0.0";
  const displayVersion = formatBuildVersion(buildVersion);
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
    if (!authenticated) {
      return;
    }
    loadConfig();
    loadStatus();
    loadErrors();
  }, [authenticated, loadConfig, loadStatus, loadErrors]);

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
    if (!authenticated) {
      return () => undefined;
    }
    const intervalMs = status?.state === "jellyfin" ? 1000 : 3000;
    const interval = setInterval(loadStatus, intervalMs);
    return () => clearInterval(interval);
  }, [authenticated, loadStatus, status?.state]);

  useEffect(() => {
    if (!authenticated) {
      return () => undefined;
    }
    const interval = setInterval(loadErrors, 10000);
    return () => clearInterval(interval);
  }, [authenticated, loadErrors]);

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

  const openSettings = (tab: "sync" | "jellyfin" | "logs" = "sync") => {
    setSettingsTab(tab);
    setViewMode("settings");
  };
  const handleCloseSettings = () => setViewMode("dashboard");
  const handleOpenLogs = (tab: "activity" | "errors" = "activity") => {
    setLogTab(tab);
    openSettings("logs");
  };
  const handleJellyfinTasksStart = (next?: SyncStatus) => {
    if (next) {
      setStatus(next);
    }
    setViewMode("dashboard");
  };

  const handleAuthSession = useCallback(
    async (session: AuthResponse, rememberMe: boolean) => {
      persistSession(session.token, session.expires_at, { remember: rememberMe });
      setAuthConfigured(true);
      setAuthenticated(true);
      setViewMode("dashboard");
      await loadConfig();
      await loadStatus();
      await loadErrors();
    },
    [loadConfig, loadErrors, loadStatus]
  );

  const refreshAuth = useCallback(async () => {
    setCheckingAuth(true);
    try {
      const statusPayload = await fetchAuthStatus();
      setAuthConfigured(statusPayload.configured);
      setAuthenticated(statusPayload.authenticated);
      if (statusPayload.authenticated) {
        await loadConfig();
        await loadStatus();
        await loadErrors();
      } else {
        setConfig(null);
        setStatus(null);
        setErrors([]);
      }
    } catch (error) {
      console.error(error);
      toast.error("Unable to verify authentication");
    } finally {
      setCheckingAuth(false);
    }
  }, [loadConfig, loadErrors, loadStatus]);

  useEffect(() => {
    const stored = getStoredSession();
    if (!stored) {
      clearStoredSession();
    }
    refreshAuth();
  }, [refreshAuth]);

  const handleLogout = async () => {
    try {
      await logoutRequest();
    } catch (error) {
      console.error(error);
    }
    clearStoredSession();
    setAuthenticated(false);
    setConfig(null);
    setStatus(null);
    setErrors([]);
    setAuthConfigured(true);
  };

  if (checkingAuth || authConfigured === null) {
    return (
      <>
        <Toaster position="bottom-right" />
        <div className="auth-container">
          <div className="auth-card">
            <p>Checking authentication…</p>
          </div>
        </div>
        <SiteFooter />
      </>
    );
  }

  if (authConfigured === false) {
    return (
      <>
        <Toaster position="bottom-right" />
        <AuthSetup onAuthenticated={handleAuthSession} />
        <SiteFooter />
      </>
    );
  }

  if (!authenticated) {
    return (
      <>
        <Toaster position="bottom-right" />
          <AuthLogin
            onAuthenticated={handleAuthSession}
            buildVersion={buildVersion}
            updateAvailable={updateAvailable}
            latestVersion={latestVersion}
        />
        <SiteFooter />
      </>
    );
  }

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
                  aria-label={`Build version ${displayVersion}`}
                >
                  <span className="header-version-text">{displayVersion}</span>
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
              <button className="primary-btn" onClick={() => openSettings("sync")} aria-label="Settings">
                Settings
              </button>
              <button className="secondary-btn" onClick={handleLogout} aria-label="Logout">
                Logout
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
      ) : viewMode === "settings" ? (
        <div className="settings-page">
          <div className="settings-panel" data-tab-style="underline">
            <header className="settings-header">
              <div>
                <h1>Settings</h1>
              </div>
              <div className="flex-row button-group">
                <button className="secondary-btn" type="button" onClick={handleCloseSettings}>
                  Back to dashboard
                </button>
              </div>
            </header>
            <div className="settings-tabs" role="tablist">
              {SETTINGS_TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={settingsTab === tab.id}
                  className={`settings-tab ${
                    settingsTab === tab.id ? "primary-btn active" : "secondary-btn"
                  }`}
                  onClick={() => setSettingsTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="settings-content">
              {settingsTab === "sync" && (
                <>
                  <div className="settings-tab-actions">
                    <button
                      className="primary-btn"
                      type="submit"
                      form="sync-settings-form"
                      disabled={!configFormValid || savingConfig}
                    >
                      {savingConfig ? "Saving…" : "Save"}
                    </button>
                  </div>
                  <ConfigForm
                    config={config}
                    onSave={async (payload) => {
                      await handleSave(payload);
                    }}
                    onRevealPassword={handleRevealPassword}
                    formId="sync-settings-form"
                    onValidityChange={setConfigFormValid}
                  />
                </>
              )}
              {settingsTab === "jellyfin" && (
                <JellyfinSetup
                  onClose={handleCloseSettings}
                  onManageTasks={() => setViewMode("jellyfinTasks")}
                />
              )}
              {settingsTab === "logs" && (
                <ActivityLogView
                  initialTab={logTab}
                />
              )}
            </div>
          </div>
        </div>
      ) : viewMode === "jellyfinTasks" ? (
        <JellyfinTasksManager
          onClose={() => openSettings("jellyfin")}
          onLaunchTasks={handleJellyfinTasksStart}
        />
      ) : null}
      <SiteFooter />
    </>
  );
}
