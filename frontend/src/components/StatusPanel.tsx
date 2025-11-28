import { useEffect, useMemo, useState } from "react";
import type { SyncStatus } from "../api/types";
import { formatBytes, formatTimestamp } from "../utils/format";

type Props = {
  status: SyncStatus | null;
  onStart: () => Promise<void>;
  onStop: () => Promise<void>;
  starting: boolean;
  stopping: boolean;
  canStart: boolean;
  errorCount: number;
  onOpenErrorLog: () => void;
};

const stateColors: Record<string, string> = {
  idle: "#003459",
  connecting: "#003459",
  scanning: "#003459",
  downloading: "#007ea7",
  stopping: "#00a7e1",
  error: "#003459",
  jellyfin: "#00171f"
};

function formatCountdown(seconds: number): string {
  const clamped = Math.max(0, seconds);
  const hrs = Math.floor(clamped / 3600);
  const mins = Math.floor((clamped % 3600) / 60);
  const secs = clamped % 60;
  const parts = [hrs, mins, secs].map((val) => String(val).padStart(2, "0"));
  return parts.join(":");
}

export function StatusPanel({
  status,
  onStart,
  onStop,
  starting,
  stopping,
  canStart,
  errorCount,
  onOpenErrorLog
}: Props) {
  const state = status?.state ?? "idle";
  const color = stateColors[state] ?? "#2563eb";
  const nextSyncTimestamp = status?.next_sync_time ? status.next_sync_time * 1000 : null;
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!nextSyncTimestamp) {
      return;
    }
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(tick);
  }, [nextSyncTimestamp]);

  const countdownSeconds = useMemo(() => {
    if (!nextSyncTimestamp) return null;
    return Math.max(0, Math.round((nextSyncTimestamp - now) / 1000));
  }, [nextSyncTimestamp, now]);

  const disableStart =
    !canStart ||
    starting ||
    stopping ||
    state === "downloading" ||
    state === "connecting" ||
    state === "scanning" ||
    state === "jellyfin";
  const disableStop = stopping;

  return (
    <div className="card">
      <h2>Current Activity</h2>
      <div className="status-grid">
        <div className="status-tile">
          <h3>Status</h3>
          <p style={{ color }}>{state.toUpperCase()}</p>
          <small className="muted">
            {state === "downloading" && status?.download_speed
              ? `${status?.message ?? "Downloading…"} ${status.download_speed}`
              : status?.message ?? "Waiting for next sync"}
          </small>
        </div>
        <button className="status-tile status-tile-button" type="button" onClick={onOpenErrorLog}>
          <h3>Errors</h3>
          <p>{errorCount}</p>
          <small className="muted">View error log</small>
        </button>
        <div className="status-tile">
          <h3>Last sync</h3>
          <p>{formatTimestamp(status?.last_sync_time)}</p>
        </div>
        <div className="status-tile">
          <h3>Next sync</h3>
          <p>
            {nextSyncTimestamp && countdownSeconds !== null
              ? formatCountdown(countdownSeconds)
              : "No countdown"}
          </p>
          <small className="muted">
            {nextSyncTimestamp ? new Date(nextSyncTimestamp).toLocaleString() : "Not scheduled"}
          </small>
        </div>
      </div>

      <div className="progress">
        <div className="progress-bar">
          <div className="progress-value" style={{ width: `${status?.progress ?? 0}%` }} />
          <span className="progress-label">{`${status?.progress ?? 0}%`}</span>
        </div>
      </div>

      {(status?.active_file || status?.target_path) && (
        <div className="status-meta">
          {status?.active_file && (
            <span>
              <strong>Active file:</strong> {status.active_file}
            </span>
          )}
          {status?.target_path && (
            <span>
              <strong>Target path:</strong> {status.target_path}
            </span>
          )}
        </div>
      )}

      <div className="flex-row">
        <button className="primary-btn" onClick={onStart} disabled={disableStart}>
          {starting ? "Starting…" : "Start sync"}
        </button>
        <button className="secondary-btn" onClick={onStop} disabled={disableStop}>
          {stopping ? "Stopping…" : "Stop run"}
        </button>
      </div>
    </div>
  );
}
