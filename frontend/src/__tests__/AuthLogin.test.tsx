import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { AuthLogin } from "../components/AuthLogin";

vi.mock("../api/service", () => ({
  login: vi.fn(),
}));

const mockedServices = vi.mocked(await import("../api/service"), true);

describe("AuthLogin", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("prefills and persists the remembered username", async () => {
    localStorage.setItem("sshyphon_username", "remembered-user");

    mockedServices.login.mockResolvedValue({
      token: "abc123",
      expires_at: Math.round(Date.now() / 1000) + 3600,
    });

    const onAuthenticated = vi.fn();

    render(
      <AuthLogin
        onAuthenticated={onAuthenticated}
        buildVersion="1.0.0"
        updateAvailable={false}
        latestVersion={"1.0.0"}
      />
    );

    expect(screen.getByLabelText(/username/i)).toHaveValue("remembered-user");

    await userEvent.type(screen.getByLabelText(/password/i), "secret");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalled());

    expect(mockedServices.login).toHaveBeenCalledWith({
      username: "remembered-user",
      password: "secret",
      remember_me: true,
    });
    expect(localStorage.getItem("sshyphon_username")).toBe("remembered-user");
    expect(onAuthenticated).toHaveBeenCalledWith(
      { token: "abc123", expires_at: expect.any(Number) },
      true
    );
  });

  it("clears remembered usernames and uses a session-only login when unchecked", async () => {
    localStorage.setItem("sshyphon_username", "old-user");

    mockedServices.login.mockResolvedValue({
      token: "short-lived", 
      expires_at: Math.round(Date.now() / 1000) + 3600,
    });

    const onAuthenticated = vi.fn();

    render(
      <AuthLogin
        onAuthenticated={onAuthenticated}
        buildVersion="1.0.0"
        updateAvailable={false}
        latestVersion={"1.0.0"}
      />
    );

    const usernameInput = screen.getByLabelText(/username/i);
    await userEvent.clear(usernameInput);
    await userEvent.type(usernameInput, "   new-user   ");
    await userEvent.type(screen.getByLabelText(/password/i), "secret");

    const rememberCheckbox = screen.getByLabelText(/remember me/i);
    await userEvent.click(rememberCheckbox);

    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalled());

    expect(mockedServices.login).toHaveBeenCalledWith({
      username: "new-user",
      password: "secret",
      remember_me: false,
    });
    expect(localStorage.getItem("sshyphon_username")).toBeNull();
    expect(onAuthenticated).toHaveBeenCalledWith(
      { token: "short-lived", expires_at: expect.any(Number) },
      false
    );
  });
});
