import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { vi } from "vitest";

import { ConfigForm } from "../components/ConfigForm";
import type { ConfigResponse } from "../api/types";

const baseConfig: ConfigResponse = {
  host: "example.com",
  port: 22,
  username: "demo",
  password: "********",
  remote_root: "/remote",
  local_root: "/local",
  skip_folders: ["cache"],
  sync_interval_minutes: 120,
  auto_sync_enabled: false,
  start_after: null,
  has_password: true,
  last_sync_time: null,
};

describe("ConfigForm", () => {
  it("normalizes skip folders and submits the payload", async () => {
    const handleSave = vi.fn().mockResolvedValue(undefined);

    render(<ConfigForm config={baseConfig} onSave={handleSave} />);

    const skipField = screen.getByLabelText(/Skip Folders/i);
    await userEvent.clear(skipField);
    await userEvent.type(skipField, "cache, tmp ");

    const toggle = screen.getByLabelText(/Enable automatic sync/i);
    fireEvent.click(toggle);

    const form = screen.getByText(/Edit Settings/).closest("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    await waitFor(() => expect(handleSave).toHaveBeenCalledTimes(1));
    const payload = handleSave.mock.calls[0][0];
    expect(payload.skip_folders).toEqual(["cache", "tmp"]);
    expect(payload.auto_sync_enabled).toBe(true);
  });

  it("reveals the stored password when requested", async () => {
    const revealPassword = vi.fn().mockResolvedValue("secret123");

    render(<ConfigForm config={baseConfig} onSave={vi.fn()} onRevealPassword={revealPassword} />);

    const togglePassword = screen.getByRole("button", { name: /show/i });
    await userEvent.click(togglePassword);

    await waitFor(() => expect(revealPassword).toHaveBeenCalled());
    const passwordInput = screen.getByLabelText(/Password/i) as HTMLInputElement;
    expect(passwordInput.value).toBe("secret123");
  });

  it("tracks validity for required fields", async () => {
    const handleValidity = vi.fn();

    render(<ConfigForm config={{ ...baseConfig, host: "" }} onSave={vi.fn()} onValidityChange={handleValidity} />);

    await waitFor(() => expect(handleValidity).toHaveBeenCalledWith(false));

    const hostInput = screen.getByLabelText(/SFTP Host/i);
    await userEvent.type(hostInput, "example.com");

    await waitFor(() => expect(handleValidity).toHaveBeenCalledWith(true));
  });

  it("keeps masked password when no reveal handler is provided", async () => {
    render(<ConfigForm config={baseConfig} onSave={vi.fn()} />);

    const togglePassword = screen.getByRole("button", { name: /show/i });
    await userEvent.click(togglePassword);

    const passwordInput = screen.getByLabelText(/Password/i) as HTMLInputElement;
    expect(passwordInput.value).toBe("********");
  });
});
