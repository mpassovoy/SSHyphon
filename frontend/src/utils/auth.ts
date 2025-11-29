const TOKEN_KEY = "sshyphon_auth_token";
const EXPIRES_KEY = "sshyphon_auth_expires_at";
const USERNAME_KEY = "sshyphon_username";

export interface StoredSession {
  token: string;
  expiresAt: number;
}

function saveSession(storage: Storage, token: string, expiresAt: number): void {
  storage.setItem(TOKEN_KEY, token);
  storage.setItem(EXPIRES_KEY, String(expiresAt));
}

function clearSession(storage: Storage): void {
  storage.removeItem(TOKEN_KEY);
  storage.removeItem(EXPIRES_KEY);
}

export function persistSession(
  token: string,
  expiresAt: number,
  options?: { remember?: boolean }
): void {
  const remember = options?.remember ?? false;
  const primaryStore = remember ? localStorage : sessionStorage;
  const secondaryStore = remember ? sessionStorage : localStorage;

  saveSession(primaryStore, token, expiresAt);
  clearSession(secondaryStore);
}

export function clearStoredSession(): void {
  clearSession(localStorage);
  clearSession(sessionStorage);
}

export function persistUsername(username: string): void {
  localStorage.setItem(USERNAME_KEY, username.trim());
}

export function clearRememberedUsername(): void {
  localStorage.removeItem(USERNAME_KEY);
}

export function getRememberedUsername(): string | null {
  return localStorage.getItem(USERNAME_KEY);
}

export function getStoredSession(): StoredSession | null {
  const stores: Storage[] = [localStorage, sessionStorage];

  for (const storage of stores) {
    const token = storage.getItem(TOKEN_KEY);
    const expiresRaw = storage.getItem(EXPIRES_KEY);

    if (!token || !expiresRaw) {
      continue;
    }

    const expiresAt = Number(expiresRaw);
    if (!Number.isFinite(expiresAt) || expiresAt <= Date.now() / 1000) {
      clearSession(storage);
      continue;
    }

    return { token, expiresAt };
  }

  return null;
}
