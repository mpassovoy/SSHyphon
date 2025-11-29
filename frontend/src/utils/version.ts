export function formatBuildVersion(version: string): string {
  const sanitizedVersion = version.trim();
  return sanitizedVersion.startsWith("v") ? sanitizedVersion : `v${sanitizedVersion}`;
}
