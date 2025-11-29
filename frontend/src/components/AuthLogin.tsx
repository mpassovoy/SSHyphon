import { FormEvent, useState } from "react";
import toast from "react-hot-toast";

import { login } from "../api/service";
import type { AuthResponse } from "../api/types";
import { clearRememberedUsername, getRememberedUsername, persistUsername } from "../utils/auth";

interface AuthLoginProps {
  onAuthenticated: (session: AuthResponse, rememberMe: boolean) => void;
  buildVersion: string;
  updateAvailable: boolean;
  latestVersion?: string | null;
}

export function AuthLogin({
  onAuthenticated,
  buildVersion,
  updateAvailable,
  latestVersion
}: AuthLoginProps) {
  const [username, setUsername] = useState(() => getRememberedUsername() ?? "");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(() => Boolean(getRememberedUsername()));
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const normalizedUsername = username.trim();
    if (!normalizedUsername) {
      setErrorMessage("Username is required");
      return;
    }
    setLoading(true);
    setErrorMessage("");
    try {
      const session = await login({
        username: normalizedUsername,
        password,
        remember_me: rememberMe,
      });
      if (rememberMe) {
        persistUsername(normalizedUsername);
      } else {
        clearRememberedUsername();
      }
      toast.success("Signed in");
      onAuthenticated(session, rememberMe);
    } catch (error: any) {
      const detail = error?.response?.data?.detail ?? "Unable to sign in";
      toast.error(detail);
      setErrorMessage(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-shell">
        <header className="app-header auth-page-header">
          <div className="logo-with-icon">
            <img src="/icons/icon_256.png" alt="SSHyphon icon" className="header-icon" />
            <div className="header-title">
              <h1>SSHyphon</h1>
              <div className="header-version" aria-label={`Build version ${buildVersion}`}>
                <span className="header-version-text">v{buildVersion}</span>
                {updateAvailable && latestVersion && (
                  <span
                    className="header-version-icon"
                    title={`Update available: ${latestVersion}`}
                  >
                    <svg viewBox="0 0 16 16" role="img" focusable="false">
                      <circle
                        cx="8"
                        cy="8"
                        r="7"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.2"
                      />
                      <path
                        d="M8.5 4.5 8.5 9.5M5 6.5 8.5 3 12 6.5"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                )}
              </div>
            </div>
          </div>
        </header>
        <div className="auth-container">
          <div className="auth-card">
            <div className="auth-header">
              <h1>Sign in to SSHyphon</h1>
            </div>
            {errorMessage && <p className="auth-error" role="alert">{errorMessage}</p>}
            <form className="auth-form" onSubmit={handleSubmit}>
              <label className="auth-label">
                Username
                <input
                  className="auth-input"
                  value={username}
                  onChange={(event) => {
                    setUsername(event.target.value);
                    setErrorMessage("");
                  }}
                  autoComplete="username"
                  required
                />
              </label>
              <label className="auth-label">
                Password
                <input
                  className="auth-input"
                  type="password"
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    setErrorMessage("");
                  }}
                  autoComplete="current-password"
                  required
                />
              </label>
              <label className="auth-checkbox">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(event) => setRememberMe(event.target.checked)}
                />
                <span>Remember me</span>
              </label>
              <button className="primary-btn auth-submit" type="submit" disabled={loading}>
                {loading ? "Signing in…" : "Sign in"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
