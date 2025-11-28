import { useEffect, useMemo, useState } from "react";
import type { FileTransfer, SyncStats } from "../api/types";
import { formatBytes, formatDateTime } from "../utils/format";

type Props = {
  transfers: FileTransfer[];
  stats: SyncStats;
};

const statusLabel: Record<FileTransfer["status"], string> = {
  "in-progress": "In-Progress",
  success: "Complete",
  failure: "Failed"
};

const PAGE_SIZES = [10, 25, 50, 100];

export function TransfersTable({ transfers, stats }: Props) {
  if (!transfers.length) {
    return (
      <div className="card">
        <h2>Recent Transfers</h2>
        <p className="muted">No transfers recorded yet.</p>
      </div>
    );
  }

  const [pageSize, setPageSize] = useState(PAGE_SIZES[0]);
  const [page, setPage] = useState(1);

  const totalPages = Math.max(1, Math.ceil(transfers.length / pageSize));

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const pagedTransfers = useMemo(() => {
    const start = (page - 1) * pageSize;
    return transfers.slice(start, start + pageSize);
  }, [page, pageSize, transfers]);

  const handlePageSizeChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setPageSize(Number(event.target.value));
    setPage(1);
  };

  const rangeStart = (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, transfers.length);

  const derivedFilesDownloaded = transfers.filter((transfer) => transfer.status === "success").length;
  const derivedBytesDownloaded = transfers
    .filter((transfer) => transfer.status === "success")
    .reduce((sum, transfer) => sum + transfer.size, 0);
  const displayFiles = stats.files_downloaded > 0 ? stats.files_downloaded : derivedFilesDownloaded;
  const displayBytes = stats.bytes_downloaded > 0 ? stats.bytes_downloaded : derivedBytesDownloaded;

  return (
    <div className="card">
      <div className="card-header-row">
        <h2>Recent Transfers</h2>
        <div className="files-synced-inline">
          Files Synced: {displayFiles}, {formatBytes(displayBytes)}
        </div>
      </div>
      <div className="table-controls">
        <label className="table-rows-select">
          Rows per page
          <select value={pageSize} onChange={handlePageSizeChange}>
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <div className="pagination-controls">
          <span className="muted">
            Showing {rangeStart}-{rangeEnd} of {transfers.length}
          </span>
          <div className="pagination-buttons">
            <button
              className="secondary-btn"
              type="button"
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              disabled={page === 1}
            >
              Prev
            </button>
            <span className="muted">
              Page {page} / {totalPages}
            </span>
            <button
              className="secondary-btn"
              type="button"
              onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
              disabled={page === totalPages}
            >
              Next
            </button>
          </div>
        </div>
      </div>
      <div className="transfers-table-wrapper">
        <table className="transfers-table">
          <thead>
            <tr>
              <th>File name</th>
              <th>Size</th>
              <th className="col-target">Target path</th>
              <th className="col-completed">Completed at</th>
              <th>Status</th>
              <th className="col-error">Error</th>
            </tr>
          </thead>
          <tbody>
            {pagedTransfers.map((transfer) => (
              <tr key={`${transfer.filename}-${transfer.target_path}`}>
                <td>{transfer.filename}</td>
                <td>{formatBytes(transfer.size)}</td>
                <td className="col-target">{transfer.target_path}</td>
                <td className="col-completed">{transfer.completed_at ? formatDateTime(transfer.completed_at) : "—"}</td>
                <td>
                  <span className={`chip ${transfer.status === "success" ? "success" : transfer.status === "failure" ? "failure" : "progress"}`}>
                    {statusLabel[transfer.status]}
                  </span>
                </td>
                <td className="col-error">{transfer.error_message ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
