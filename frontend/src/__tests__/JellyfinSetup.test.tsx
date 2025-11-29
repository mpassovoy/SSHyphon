import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { JellyfinSetup } from "../components/JellyfinSetup";
import type { JellyfinConfigResponse } from "../api/types";

const toast = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn()
}));

vi.mock("react-hot-toast", () => ({
  __esModule: true,
  default: toast
}));

const fetchJellyfinConfig = vi.fn();
const testJellyfinConnection = vi.fn();
const updateJellyfinConfig = vi.fn();

vi.mock("../api/service", () => ({
  fetchJellyfinConfig: (...args: unknown[]) => fetchJellyfinConfig(...args),
  testJellyfinConnection: (...args: unknown[]) => testJellyfinConnection(...args),
  updateJellyfinConfig: (...args: unknown[]) => updateJellyfinConfig(...args)
}));

const baseConfig: JellyfinConfigResponse = {
  server_url: "http://jf",
  api_key: "",
  has_api_key: true,
  tested: true,
  include_hidden_tasks: false,
  selected_tasks: []
};

const renderSetup = () =>
  render(<JellyfinSetup onClose={vi.fn()} onManageTasks={vi.fn()} />);

describe("JellyfinSetup", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchJellyfinConfig.mockResolvedValue(baseConfig);
    updateJellyfinConfig.mockResolvedValue(baseConfig);
    testJellyfinConnection.mockResolvedValue(undefined);
  });

  it("reveals the stored API key when toggled", async () => {
    fetchJellyfinConfig.mockResolvedValueOnce(baseConfig);
    fetchJellyfinConfig.mockResolvedValueOnce({ ...baseConfig, api_key: "real-key" });

    renderSetup();

    const reveal = await screen.findByRole("button", { name: /show/i });
    await userEvent.click(reveal);

    await waitFor(() => expect(fetchJellyfinConfig).toHaveBeenLastCalledWith({ reveal: true }));
    const input = screen.getByLabelText(/API Key/i) as HTMLInputElement;
    expect(input.value).toBe("real-key");
  });

  it("disables managing tasks while configuration is dirty", async () => {
    renderSetup();
    await screen.findByText(/Connection status/i);

    const serverInput = screen.getByLabelText(/Server URL/i);
    await userEvent.type(serverInput, "example");

    const manageBtn = screen.getByRole("button", { name: /Manage tasks/i });
    expect(manageBtn).toBeDisabled();
    expect(manageBtn).toHaveAttribute("title", expect.stringContaining("Save settings"));
  });

  it("surfaces save failures", async () => {
    updateJellyfinConfig.mockRejectedValueOnce(new Error("bad save"));

    renderSetup();
    const save = await screen.findByRole("button", { name: /^Save$/i });
    await userEvent.click(save);

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Unable to save Jellyfin settings"));
  });

  it("shows test error details from the API", async () => {
    testJellyfinConnection.mockRejectedValueOnce({ response: { data: { detail: "bad test" } } });
    fetchJellyfinConfig.mockResolvedValueOnce({ ...baseConfig, has_api_key: false, api_key: "abc" });

    renderSetup();
    const testBtn = await screen.findByRole("button", { name: /Test connection/i });
    await userEvent.click(testBtn);

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("bad test"));
  });
});
