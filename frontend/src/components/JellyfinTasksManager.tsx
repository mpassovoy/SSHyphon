import { useEffect, useMemo, useRef, useState } from "react";
import type { JellyfinConfigResponse, JellyfinSelectedTask, JellyfinTask, SyncStatus } from "../api/types";
import { fetchJellyfinConfig, fetchJellyfinTasks, runJellyfinTasks, updateJellyfinConfig } from "../api/service";
import toast from "react-hot-toast";

type Props = {
  onClose: () => void;
  onLaunchTasks: (status?: SyncStatus) => void;
};

export function JellyfinTasksManager({ onClose, onLaunchTasks }: Props) {
  const [config, setConfig] = useState<JellyfinConfigResponse | null>(null);
  const [tasks, setTasks] = useState<JellyfinTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [startingRun, setStartingRun] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const load = async () => {
      try {
        const cfg = await fetchJellyfinConfig();
        setConfig(cfg);
        const allTasks = await fetchJellyfinTasks();
        setTasks(allTasks);
      } catch (error) {
        console.error(error);
        toast.error("Unable to load Jellyfin tasks");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const selectedByKey: Record<string, JellyfinSelectedTask> = useMemo(() => {
    const map: Record<string, JellyfinSelectedTask> = {};
    (config?.selected_tasks ?? []).forEach((t) => {
      const key = t.key || t.legacy_id || t.name;
      if (key) {
        map[key] = t;
      }
    });
    return map;
  }, [config]);

  const orderedTasks = useMemo(() => {
    return [...tasks].sort((a, b) => {
      const sa = selectedByKey[a.key];
      const sb = selectedByKey[b.key];
      if (sa && sb) return sa.order - sb.order;
      if (sa) return -1;
      if (sb) return 1;
      return a.name.localeCompare(b.name);
    });
  }, [tasks, selectedByKey]);

  const toggleTask = (task: JellyfinTask) => {
    if (!config) return;
    const lookupKey = task.key || task.id;
    const existing = lookupKey ? selectedByKey[lookupKey] : undefined;
    let nextSelected: JellyfinSelectedTask[];
    if (existing) {
      nextSelected = config.selected_tasks.filter((t) => (t.key || t.legacy_id || t.name) !== lookupKey);
    } else {
      const maxOrder = config.selected_tasks.reduce((max, t) => Math.max(max, t.order), 0);
      nextSelected = [
        ...config.selected_tasks,
        {
          key: task.key || task.id || task.name,
          legacy_id: task.id,
          name: task.name,
          enabled: true,
          order: maxOrder + 1
        }
      ];
    }
    setConfig({ ...config, selected_tasks: nextSelected });
  };

  const moveTask = (taskId: string, direction: "up" | "down") => {
    if (!config) return;
    const items = [...config.selected_tasks].sort((a, b) => a.order - b.order);
    const index = items.findIndex((t) => (t.key || t.legacy_id || t.name) === taskId);
    if (index === -1) return;
    const swapWith = direction === "up" ? index - 1 : index + 1;
    if (swapWith < 0 || swapWith >= items.length) return;
    const tmp = items[index].order;
    items[index].order = items[swapWith].order;
    items[swapWith].order = tmp;
    setConfig({ ...config, selected_tasks: items });
  };

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const payload = {
        ...config,
        selected_tasks: config.selected_tasks
      };
      const updated = await updateJellyfinConfig(payload);
      setConfig(updated);
      toast.success("Jellyfin tasks updated");
      onClose();
    } catch (error) {
      console.error(error);
      toast.error("Unable to save Jellyfin tasks");
    } finally {
      setSaving(false);
    }
  };

  const handleStartRun = () => {
    if (!config?.tested) {
      toast.error("Test the Jellyfin connection before starting tasks.");
      return;
    }
    setStartingRun(true);
    runJellyfinTasks()
      .then((status) => {
        toast.success("Jellyfin tasks started");
        onLaunchTasks(status);
      })
      .catch((error: any) => {
        console.error(error);
        toast.error(error?.response?.data?.detail ?? "Unable to start Jellyfin tasks");
      })
      .finally(() => {
        if (mountedRef.current) {
          setStartingRun(false);
        }
      });
  };

  if (loading) {
    return (
      <div className="config-view">
        <div className="config-header">
          <h1>Jellyfin Tasks</h1>
        </div>
        <p className="muted">Loading scheduled tasks…</p>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="config-view">
        <div className="config-header">
          <h1>Jellyfin Tasks</h1>
        </div>
        <p className="muted">Unable to load Jellyfin configuration.</p>
      </div>
    );
  }

  return (
    <div className="config-view">
        <div className="config-header">
          <h1>Jellyfin Tasks</h1>
          <div className="flex-row button-group">
            <button className="secondary-btn" type="button" onClick={onClose}>
              Back
            </button>
            <button className="secondary-btn" type="button" onClick={handleStartRun} disabled={startingRun || !config.tested}>
              {startingRun ? "Starting…" : "Start Tasks"}
            </button>
            <button className="primary-btn" type="button" onClick={handleSave} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>

      <div className="card">
        {tasks.length === 0 ? (
          <p className="muted">No Jellyfin scheduled tasks were returned.</p>
        ) : (
          <table className="transfers-table">
            <thead>
              <tr>
                <th>Run</th>
                <th>Task</th>
                <th>Description</th>
                <th>Order</th>
              </tr>
            </thead>
            <tbody>
              {orderedTasks.map((task) => {
                const selected = selectedByKey[task.key];
                return (
                  <tr key={task.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={!!selected}
                        onChange={() => toggleTask(task)}
                      />
                    </td>
                    <td>{task.name}</td>
                    <td className="muted">{task.description || "—"}</td>
                    <td>
                      {selected ? (
                        <div className="flex-row">
                          <button
                            type="button"
                            className="secondary-btn"
                            style={{ padding: "0.25rem 0.5rem" }}
                            onClick={() => moveTask(task.key, "up")}
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            className="secondary-btn"
                            style={{ padding: "0.25rem 0.5rem" }}
                            onClick={() => moveTask(task.key, "down")}
                          >
                            ↓
                          </button>
                        </div>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
