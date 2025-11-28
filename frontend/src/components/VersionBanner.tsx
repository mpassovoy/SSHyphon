import type { VersionInfo } from "../api/types";

interface VersionBannerProps {
  buildVersion: string;
  info: VersionInfo | null;
  status: "loading" | "ready" | "error";
  onRetry: () => Promise<void> | void;
}

export function VersionBanner({ buildVersion, info, status, onRetry }: VersionBannerProps) {
  const runtimeVersion = info?.version ?? "unknown";
  const versionsMatch = info?.version ? info.version === buildVersion : false;
  const updateAvailable = info?.update_available && info.latest_version;
  const repositoryConfigured = info?.repository;
  const pillClassName = versionsMatch && status === "ready"
    ? "version-pill version-pill-ok"
    : status === "ready"
      ? "version-pill version-pill-warning"
      : "version-pill";

  return (
    <div className="version-banner">
      <div className={pillClassName}>
        <span className="version-label">Build</span>
        <span className="version-value">{buildVersion}</span>
        {versionsMatch && <span className="version-status">runtime verified</span>}
      </div>
      <div className="version-detail">
        {status === "loading" && <span>Checking runtime version…</span>}
        {status === "ready" && (
          <span>
            Runtime {runtimeVersion}
            {!versionsMatch && " (mismatch)"}
          </span>
        )}
        {status === "error" && (
          <span>
            Unable to read runtime version. <button onClick={onRetry}>Retry</button>
          </span>
        )}
      </div>
      <div className="version-latest">
        {status === "ready" && updateAvailable && (
          <span className="update-pill">Update available: {info?.latest_version}</span>
        )}
        {status === "ready" && !updateAvailable && info?.latest_version && (
          <span>Latest release: {info.latest_version}</span>
        )}
        {status === "ready" && !info?.latest_version && repositoryConfigured && <span>Latest release not found</span>}
        {status === "ready" && !info?.latest_version && !repositoryConfigured && <span>Update check unavailable</span>}
      </div>
    </div>
  );
}
