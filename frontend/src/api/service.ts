import { apiClient } from "./client";
import {
  ConfigResponse,
  JellyfinConfig,
  JellyfinConfigResponse,
  JellyfinTask,
  JellyfinTestPayload,
  SftpConfig,
  SyncStatus,
  VersionInfo
} from "./types";

export async function fetchConfig(options?: { reveal?: boolean }): Promise<ConfigResponse> {
  const params = options?.reveal ? { reveal: true } : undefined;
  const { data } = await apiClient.get<ConfigResponse>("/config", { params });
  return data;
}

export async function updateConfig(payload: SftpConfig): Promise<ConfigResponse> {
  const { data } = await apiClient.put<ConfigResponse>("/config", payload);
  return data;
}

export async function fetchStatus(): Promise<SyncStatus> {
  const { data } = await apiClient.get<SyncStatus>("/status");
  return data;
}

export async function startSync(): Promise<SyncStatus> {
  const { data } = await apiClient.post<SyncStatus>("/sync/start");
  return data;
}

export async function stopSync(): Promise<SyncStatus> {
  const { data } = await apiClient.post<SyncStatus>("/sync/stop");
  return data;
}

export async function fetchErrors(limit = 200): Promise<string[]> {
  const { data } = await apiClient.get<{ errors: string[] }>("/errors", {
    params: { limit }
  });
  return data.errors ?? [];
}

export async function fetchActivityLog(limit = 1000): Promise<string[]> {
  const { data } = await apiClient.get<{ entries: string[] }>("/activity/log", {
    params: { limit }
  });
  return data.entries ?? [];
}

export async function clearActivityLog(): Promise<void> {
  await apiClient.post("/activity/clear");
}

export async function clearErrorLog(): Promise<void> {
  await apiClient.post("/errors/clear");
}

export async function fetchJellyfinConfig(options?: { reveal?: boolean }): Promise<JellyfinConfigResponse> {
  const params = options?.reveal ? { reveal: true } : undefined;
  const { data } = await apiClient.get<JellyfinConfigResponse>("/jellyfin/config", { params });
  return data;
}

export async function updateJellyfinConfig(payload: JellyfinConfig): Promise<JellyfinConfigResponse> {
  const { data } = await apiClient.put<JellyfinConfigResponse>("/jellyfin/config", payload);
  return data;
}

export async function testJellyfinConnection(payload?: JellyfinTestPayload): Promise<void> {
  await apiClient.post("/jellyfin/test", payload ?? {});
}

export async function fetchJellyfinTasks(): Promise<JellyfinTask[]> {
  const { data } = await apiClient.get<JellyfinTask[]>("/jellyfin/tasks");
  return data;
}

export async function runJellyfinTasks(): Promise<SyncStatus> {
  const { data } = await apiClient.post<SyncStatus>("/jellyfin/tasks/run");
  return data;
}

export async function fetchVersionInfo(): Promise<VersionInfo> {
  const { data } = await apiClient.get<VersionInfo>("/version");
  return data;
}
