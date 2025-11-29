export type SyncState =
  | "idle"
  | "connecting"
  | "scanning"
  | "downloading"
  | "stopping"
  | "error"
  | "jellyfin";

export interface SftpConfig {
  host: string;
  port: number;
  username: string;
  password: string;
  remote_root: string;
  local_root: string;
  skip_folders: string[];
  sync_interval_minutes: number;
  auto_sync_enabled: boolean;
  start_after: string | null;
}

export interface ConfigResponse extends SftpConfig {
  has_password: boolean;
  last_sync_time?: number | null;
}

export interface SyncStats {
  files_downloaded: number;
  bytes_downloaded: number;
  errors: number;
}

export interface FileTransfer {
  filename: string;
  size: number;
  target_path: string;
  status: "in-progress" | "success" | "failure";
  completed_at?: string | null;
  error_message?: string | null;
}

export interface SyncStatus {
  state: SyncState;
  message: string;
  active_file?: string | null;
  target_path?: string | null;
  progress: number;
  download_speed?: string | null;
  stats: SyncStats;
  recent_transfers: FileTransfer[];
  last_error?: string | null;
  last_sync_time?: number | null;
  next_sync_time?: number | null;
}

export interface JellyfinSelectedTask {
  key: string;
  name: string;
  enabled: boolean;
  order: number;
  legacy_id?: string;
}

export interface JellyfinConfig {
  server_url: string;
  api_key: string;
  include_hidden_tasks: boolean;
  selected_tasks: JellyfinSelectedTask[];
  tested: boolean;
}

export interface JellyfinConfigResponse extends JellyfinConfig {
  has_api_key: boolean;
}

export interface JellyfinTask {
  id: string;
  key: string;
  name: string;
  description?: string | null;
  is_hidden: boolean;
}

export interface JellyfinTestPayload {
  server_url: string;
  api_key: string;
  include_hidden_tasks?: boolean;
  persist?: boolean;
}

export interface VersionInfo {
  version: string;
  commit?: string;
  built_at?: string;
  repository?: string | null;
  latest_version?: string | null;
  update_available?: boolean;
  checked_at?: string;
}

export interface AuthStatus {
  configured: boolean;
  authenticated: boolean;
  session_expires_at?: number | null;
}

export interface AuthPayload {
  username: string;
  password: string;
  remember_me?: boolean;
}

export interface AuthResponse {
  token: string;
  expires_at: number;
}
