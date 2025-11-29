import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { JellyfinTasksManager } from "../components/JellyfinTasksManager";
import type { JellyfinConfigResponse, JellyfinTask, SyncStatus } from "../api/types";

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));

vi.mock("react-hot-toast", () => ({
  __esModule: true,
  default: toast
}));

const fetchJellyfinConfig = vi.fn();
const fetchJellyfinTasks = vi.fn();
const updateJellyfinConfig = vi.fn();
const runJellyfinTasks = vi.fn();

vi.mock("../api/service", () => ({
  fetchJellyfinConfig: (...args: unknown[]) => fetchJellyfinConfig(...args),
  fetchJellyfinTasks: (...args: unknown[]) => fetchJellyfinTasks(...args),
  updateJellyfinConfig: (...args: unknown[]) => updateJellyfinConfig(...args),
  runJellyfinTasks: (...args: unknown[]) => runJellyfinTasks(...args)
}));

const baseConfig: JellyfinConfigResponse = {
  server_url: "http://jf",
  api_key: "token",
  has_api_key: true,
  tested: true,
  include_hidden_tasks: false,
  selected_tasks: [{ key: "task-a", name: "Task A", enabled: true, order: 1 }]
};

const baseTasks: JellyfinTask[] = [
  { id: "task-a", key: "task-a", name: "Task A", description: "First", is_hidden: false },
  { id: "task-b", key: "task-b", name: "Task B", description: "Second", is_hidden: false }
];

describe("JellyfinTasksManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchJellyfinConfig.mockResolvedValue({ ...baseConfig });
    fetchJellyfinTasks.mockResolvedValue([...baseTasks]);
    updateJellyfinConfig.mockResolvedValue({ ...baseConfig });
    runJellyfinTasks.mockResolvedValue({ state: "jellyfin" } as SyncStatus);
  });

  it("prevents starting tasks when connection is untested", async () => {
    fetchJellyfinConfig.mockResolvedValueOnce({ ...baseConfig, tested: false });

    render(
      <JellyfinTasksManager onClose={vi.fn()} onLaunchTasks={vi.fn()} />
    );

    const startButton = await screen.findByRole("button", { name: /Start Tasks/i });
    expect(startButton).toBeDisabled();
    await userEvent.click(startButton);

    expect(runJellyfinTasks).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("saves selected tasks and notifies on success", async () => {
    const onClose = vi.fn();
    render(<JellyfinTasksManager onClose={onClose} onLaunchTasks={vi.fn()} />);

    const save = await screen.findByRole("button", { name: /^Save$/i });
    await userEvent.click(save);

    await waitFor(() => expect(updateJellyfinConfig).toHaveBeenCalled());
    expect(toast.success).toHaveBeenCalledWith("Jellyfin tasks updated");
    expect(onClose).toHaveBeenCalled();
  });

  it("reorders tasks when moving entries", async () => {
    fetchJellyfinConfig.mockResolvedValue({
      ...baseConfig,
      selected_tasks: [
        { key: "task-a", name: "Task A", enabled: true, order: 1 },
        { key: "task-b", name: "Task B", enabled: true, order: 2 }
      ]
    });

    render(<JellyfinTasksManager onClose={vi.fn()} onLaunchTasks={vi.fn()} />);

    const rows = await screen.findAllByRole("row");
    const firstDataRow = rows[1];
    const moveDown = within(firstDataRow).getByRole("button", { name: "↓" });
    await userEvent.click(moveDown);

    const reorderedRows = screen.getAllByRole("row");
    const firstTaskName = within(reorderedRows[1]).getByText("Task B");
    expect(firstTaskName).toBeInTheDocument();
  });

  it("surfaces loader failures", async () => {
    fetchJellyfinConfig.mockRejectedValueOnce(new Error("load fail"));

    render(<JellyfinTasksManager onClose={vi.fn()} onLaunchTasks={vi.fn()} />);

    await waitFor(() => expect(screen.getByText(/Unable to load Jellyfin configuration/i)).toBeInTheDocument());
    expect(toast.error).toHaveBeenCalled();
  });

  it("runs tasks and forwards status", async () => {
    const onLaunchTasks = vi.fn();
    runJellyfinTasks.mockResolvedValueOnce({ state: "jellyfin", progress: 0 } as SyncStatus);

    render(<JellyfinTasksManager onClose={vi.fn()} onLaunchTasks={onLaunchTasks} />);

    const startButton = await screen.findByRole("button", { name: /Start Tasks/i });
    await userEvent.click(startButton);

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Jellyfin tasks started"));
    expect(onLaunchTasks).toHaveBeenCalledWith({ state: "jellyfin", progress: 0 });
  });
});
