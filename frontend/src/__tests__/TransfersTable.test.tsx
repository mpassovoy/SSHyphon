import { render, screen } from "@testing-library/react";

import { TransfersTable } from "../components/TransfersTable";
import type { FileTransfer, SyncStats } from "../api/types";

describe("TransfersTable", () => {
  it("shows empty state when no transfers", () => {
    render(<TransfersTable transfers={[]} stats={{ files_downloaded: 0, bytes_downloaded: 0, errors: 0 }} />);

    expect(screen.getByText(/No transfers recorded yet/i)).toBeInTheDocument();
  });

  it("derives stats from successful transfers when stats are zero", () => {
    const transfers: FileTransfer[] = [
      {
        filename: "file1",
        size: 1024,
        target_path: "/tmp/file1",
        completed_at: "2024-01-01T00:00:00Z",
        status: "success"
      },
      {
        filename: "file2",
        size: 2048,
        target_path: "/tmp/file2",
        completed_at: null,
        status: "failure",
        error_message: "disk full"
      }
    ];

    const stats: SyncStats = { files_downloaded: 0, bytes_downloaded: 0, errors: 1 };

    render(<TransfersTable transfers={transfers} stats={stats} />);

    expect(screen.getByText(/Files Synced: 1, 1.00 KB/)).toBeInTheDocument();
    expect(screen.getByText(/disk full/)).toBeInTheDocument();
  });
});
