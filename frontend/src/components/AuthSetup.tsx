import { FormEvent, useState } from "react";
import toast from "react-hot-toast";

import { setupAuth } from "../api/service";
import type { AuthResponse } from "../api/types";

interface AuthSetupProps {
  onAuthenticated: (session: AuthResponse, rememberMe: boolean) => void;
}

export function AuthSetup({ onAuthenticated }: AuthSetupProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!username.trim() || !password) {
      toast.error("Username and password are required");
      return;
    }
    if (password !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }
    setSaving(true);
    try {
      const session = await setupAuth({ username, password });
      toast.success("Authentication configured");
      onAuthenticated(session, true);
    } catch (error: any) {
      const detail = error?.response?.data?.detail ?? "Unable to save credentials";
      toast.error(detail);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1>Set up SSHyphon</h1>
          <p className="auth-subtitle">Create the initial username and password to continue.</p>
        </div>
        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="auth-label">
            Username
            <input
              className="auth-input"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
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
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              required
            />
          </label>
          <label className="auth-label">
            Confirm Password
            <input
              className="auth-input"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              required
            />
          </label>
          <button className="primary-btn auth-submit" type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save and continue"}
          </button>
        </form>
      </div>
    </div>
  );
}
