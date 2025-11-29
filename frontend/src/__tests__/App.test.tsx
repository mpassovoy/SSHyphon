import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import App from "../App";
import type { ConfigResponse, SyncStatus } from "../api/types";

const { toast, toastSuccess, toastError, baseConfig, baseStatus, baseVersion } = vi.hoisted(() => {
  const toastFn = vi.fn();
  const successFn = vi.fn();
  const errorFn = vi.fn();
  const config: ConfigResponse = {
    host: "example.com",
    port: 22,
    username: "demo",
    password: "********",
    remote_root: "/remote",
    local_root: "/local",
    skip_folders: ["cache"],
    sync_interval_minutes: 120,
    auto_sync_enabled: true,
    start_after: null,
    has_password: true,
    last_sync_time: 1710000000,
  };

  const status: SyncStatus = {
    state: "idle",
    message: "Idle",
    progress: 0,
    stats: { files_downloaded: 1, bytes_downloaded: 1000, errors: 0 },
    recent_transfers: [],
    next_sync_time: Math.round(Date.now() / 1000) + 3600,
  };

  const version = {
    version: "0.0.0",
    latest_version: "0.0.0",
    update_available: false,
  };

  return {
    toast: toastFn,
    toastSuccess: successFn,
    toastError: errorFn,
    baseConfig: config,
    baseStatus: status,
    baseVersion: version,
  };
});

vi.mock("react-hot-toast", () => {
  const base = (...args: any[]) => toast(...args);
  (base as any).success = toastSuccess;
  (base as any).error = toastError;
  return { __esModule: true, default: base, Toaster: () => null };
});

vi.mock("../api/service", () => ({
  fetchAuthStatus: vi.fn().mockResolvedValue({
    configured: true,
    authenticated: true,
    session_expires_at: Math.round(Date.now() / 1000) + 3600,
  }),
  fetchConfig: vi.fn().mockResolvedValue({ ...baseConfig }),
  fetchStatus: vi.fn().mockResolvedValue({ ...baseStatus }),
  fetchVersionInfo: vi.fn().mockResolvedValue({ ...baseVersion }),
  fetchErrors: vi.fn().mockResolvedValue(["first error"]),
  fetchActivityLog: vi.fn().mockResolvedValue(["activity one"]),
  clearActivityLog: vi.fn().mockResolvedValue(undefined),
  clearErrorLog: vi.fn().mockResolvedValue(undefined),
  startSync: vi.fn().mockResolvedValue({ ...baseStatus, state: "connecting", message: "Connecting" }),
  stopSync: vi.fn().mockResolvedValue({ ...baseStatus, state: "stopping", message: "Stopping" }),
  updateConfig: vi.fn().mockResolvedValue({ ...baseConfig }),
  logout: vi.fn().mockResolvedValue(undefined),
  login: vi.fn(),
  setupAuth: vi.fn(),
}));

const mockedServices = vi.mocked(await import("../api/service"), true);

describe("App", () => {
  beforeEach(() => {
    mockedServices.fetchAuthStatus.mockResolvedValue({
      configured: true,
      authenticated: true,
      session_expires_at: Math.round(Date.now() / 1000) + 3600,
    });
    mockedServices.fetchConfig.mockResolvedValue({ ...baseConfig });
    mockedServices.fetchStatus.mockResolvedValue({ ...baseStatus });
    mockedServices.fetchVersionInfo.mockResolvedValue({ ...baseVersion });
    mockedServices.fetchErrors.mockResolvedValue(["first error"]);
    mockedServices.fetchActivityLog.mockResolvedValue(["activity one"]);
    mockedServices.clearActivityLog.mockResolvedValue(undefined);
    mockedServices.clearErrorLog.mockResolvedValue(undefined);
    mockedServices.startSync.mockResolvedValue({ ...baseStatus, state: "connecting", message: "Connecting" });
    mockedServices.stopSync.mockResolvedValue({ ...baseStatus, state: "stopping", message: "Stopping" });
    mockedServices.updateConfig.mockResolvedValue({ ...baseConfig });
    mockedServices.logout.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads initial data and starts a sync", async () => {
    render(<App />);

    await waitFor(() => expect(mockedServices.fetchConfig).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1, name: /SSHyphon/ })).toBeInTheDocument(),
    );

    const startButton = await screen.findByRole("button", { name: /start sync/i });
    expect(startButton).toBeEnabled();

    await userEvent.click(startButton);
    await waitFor(() => expect(mockedServices.startSync).toHaveBeenCalledTimes(1));
  });

  const openSettingsPanel = async () => {
    const openSettings = await screen.findByRole("button", { name: /settings/i });
    await userEvent.click(openSettings);
  };

  it("opens the config view and saves changes", async () => {
    render(<App />);

    await openSettingsPanel();

    expect(await screen.findByText(/Edit Settings/)).toBeInTheDocument();

    const saveButton = await screen.findByRole("button", { name: /save/i });
    await waitFor(() => expect(saveButton).toBeEnabled());

    await userEvent.click(saveButton);
    await waitFor(() => expect(mockedServices.updateConfig).toHaveBeenCalled());
  });

  it("prevents starting when the config is incomplete", async () => {
    mockedServices.fetchConfig.mockResolvedValue({ ...baseConfig, host: "" });

    render(<App />);

    const startButton = await screen.findByRole("button", { name: /start sync/i });
    expect(startButton).toBeDisabled();
  });

  it("shows an error toast when starting fails", async () => {
    mockedServices.startSync.mockRejectedValueOnce({ response: { data: { detail: "Sync already running" } } });

    render(<App />);

    const startButton = await screen.findByRole("button", { name: /start sync/i });
    await waitFor(() => expect(startButton).toBeEnabled());
    await userEvent.click(startButton);

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("Sync already running"));
  });

  it("shows an error toast when config load fails", async () => {
    mockedServices.fetchConfig.mockRejectedValueOnce(new Error("fail"));

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(<App />);

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("Unable to load configuration"));

    consoleSpy.mockRestore();
  });

  it("shows an error toast when stop fails", async () => {
    mockedServices.stopSync.mockRejectedValueOnce({ response: { data: { detail: "Stop failed" } } });

    render(<App />);

    const stopButton = await screen.findByRole("button", { name: /stop run/i });
    await userEvent.click(stopButton);

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("Stop failed"));
  });

  it("surfaces reveal failures in the config view", async () => {
    mockedServices.fetchConfig.mockImplementation(async (options?: { reveal?: boolean }) => {
      if (options?.reveal) {
        throw new Error("nope");
      }
      return { ...baseConfig };
    });

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(<App />);

    await openSettingsPanel();

    const revealButton = await screen.findByRole("button", { name: /show/i });
    await userEvent.click(revealButton);

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("Unable to reveal password"));

    consoleSpy.mockRestore();
  });

  it("renders the logs view and counts errors", async () => {
    render(<App />);

    await openSettingsPanel();
    const logsTab = await screen.findByRole("tab", { name: /logs/i });
    await userEvent.click(logsTab);

    expect(await screen.findByText(/Activity Log/i)).toBeInTheDocument();

    const errorTab = screen.getByRole("button", { name: /error log/i });
    await userEvent.click(errorTab);
    expect(await screen.findByText(/first error/i)).toBeInTheDocument();
  });
});
