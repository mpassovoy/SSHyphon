import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { StatusPanel } from "../components/StatusPanel";
import type { SyncStatus } from "../api/types";

describe("StatusPanel", () => {
  it("formats countdowns and disables start while running", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-01-01T00:00:00Z"));

    const status: SyncStatus = {
      state: "downloading",
      message: "Downloading",
      progress: 50,
      stats: { files_downloaded: 1, bytes_downloaded: 1000, errors: 0 },
      recent_transfers: [],
      next_sync_time: Math.round(Date.now() / 1000) + 3600,
      download_speed: "10 MB/s"
    };

    render(
      <StatusPanel
        status={status}
        starting={false}
        stopping={false}
        canStart={true}
        errorCount={0}
        onOpenErrorLog={vi.fn()}
        onStart={vi.fn()}
        onStop={vi.fn()}
      />
    );

    expect(screen.getByText(/01:00:00/)).toBeInTheDocument();
    expect(screen.getByText(/Downloading 10 MB\/s/)).toBeInTheDocument();
    const startButton = screen.getByRole("button", { name: /Start sync/i });
    expect(startButton).toBeDisabled();
    vi.useRealTimers();
  });

  it("shows metadata when available", () => {
    const status: SyncStatus = {
      state: "idle",
      message: "Idle",
      progress: 0,
      stats: { files_downloaded: 0, bytes_downloaded: 0, errors: 0 },
      recent_transfers: [],
      active_file: "movie.mkv",
      target_path: "/local/movie.mkv"
    };

    render(
      <StatusPanel
        status={status}
        starting={false}
        stopping={false}
        canStart={true}
        errorCount={0}
        onOpenErrorLog={vi.fn()}
        onStart={vi.fn()}
        onStop={vi.fn()}
      />
    );

    const active = screen.getByText(/Active file:/).parentElement;
    expect(active?.textContent).toContain("movie.mkv");
    const target = screen.getByText(/Target path:/).parentElement;
    expect(target?.textContent).toContain("/local/movie.mkv");
  });
});
