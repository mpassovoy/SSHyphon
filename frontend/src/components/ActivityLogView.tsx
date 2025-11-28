import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import {
  clearActivityLog,
  clearErrorLog,
  fetchActivityLog,
  fetchErrors
} from "../api/service";

interface Props {
  onClose: () => void;
  initialTab?: "activity" | "errors";
}

export function ActivityLogView({ onClose, initialTab = "activity" }: Props) {
  const [activeTab, setActiveTab] = useState<"activity" | "errors">(initialTab);
  const [activityEntries, setActivityEntries] = useState<string[]>([]);
  const [errorEntries, setErrorEntries] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);

  const loadEntries = async (tab = activeTab) => {
    setLoading(true);
    try {
      if (tab === "activity") {
        const lines = await fetchActivityLog();
        setActivityEntries(lines);
      } else {
        const errors = await fetchErrors(1000);
        setErrorEntries(errors);
      }
    } catch (error) {
      console.error(error);
      toast.error("Unable to load logs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setActiveTab(initialTab);
    loadEntries(initialTab);
  }, [initialTab]);

  const handleClear = async () => {
    setClearing(true);
    try {
      if (activeTab === "activity") {
        await clearActivityLog();
        toast.success("Activity log cleared");
        setActivityEntries([]);
      } else {
        await clearErrorLog();
        toast.success("Error log cleared");
        setErrorEntries([]);
      }
    } catch (error) {
      console.error(error);
      toast.error("Unable to clear log");
    } finally {
      setClearing(false);
    }
  };

  const handleDownload = async () => {
    try {
      const endpoint = activeTab === "activity" ? "/api/activity/download" : "/api/errors/download";
      const response = await fetch(endpoint);
      if (!response.ok) {
        throw new Error("Failed to download log");
      }
      const blob = await response.blob();
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
      const blobUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = blobUrl;
      anchor.download = `${activeTab}-log-${timestamp}.log`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(blobUrl);
    } catch (error) {
      console.error(error);
      toast.error("Unable to download log");
    }
  };

  const currentEntries = activeTab === "activity" ? activityEntries : errorEntries;

  return (
    <div className="config-view">
      <div className="config-header">
        <h1>Logs</h1>
        <button className="primary-btn" type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="card" style={{ minHeight: "400px" }}>
        <div className="tab-buttons" style={{ marginBottom: "1rem" }}>
          <button
            type="button"
            className={activeTab === "activity" ? "tab-btn active" : "tab-btn"}
            onClick={() => {
              setActiveTab("activity");
              loadEntries("activity");
            }}
          >
            Activity Log
          </button>
          <button
            type="button"
            className={activeTab === "errors" ? "tab-btn active" : "tab-btn"}
            onClick={() => {
              setActiveTab("errors");
              loadEntries("errors");
            }}
          >
            Error Log
          </button>
        </div>
        {loading ? (
          <p className="muted">Loading log…</p>
        ) : currentEntries.length === 0 ? (
          <p className="muted">Log is empty.</p>
        ) : (
          <div className="activity-log">
            <pre>{currentEntries.join("\n")}</pre>
          </div>
        )}
        <div className="log-action-row button-group">
          <button className="secondary-btn" type="button" onClick={() => loadEntries()} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
          <button className="secondary-btn" type="button" onClick={handleClear} disabled={clearing}>
            {clearing ? "Clearing…" : "Clear log"}
          </button>
          <button className="secondary-btn" type="button" onClick={handleDownload}>
            Download
          </button>
        </div>
      </div>
    </div>
  );
}
