import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ActivityLogView } from "../components/ActivityLogView";

const { toast, toastSuccess, toastError } = vi.hoisted(() => {
  return { toast: vi.fn(), toastSuccess: vi.fn(), toastError: vi.fn() };
});

vi.mock("react-hot-toast", () => {
  const base = (...args: any[]) => toast(...args);
  (base as any).success = toastSuccess;
  (base as any).error = toastError;
  return { __esModule: true, default: base, Toaster: () => null };
});

vi.mock("../api/service", () => ({
  fetchActivityLog: vi.fn().mockResolvedValue(["activity one"]),
  fetchErrors: vi.fn().mockResolvedValue(["error one"]),
  clearActivityLog: vi.fn().mockResolvedValue(undefined),
  clearErrorLog: vi.fn().mockResolvedValue(undefined),
}));

const mockedServices = vi.mocked(await import("../api/service"), true);

const mockFetch = vi.fn();

global.fetch = mockFetch as unknown as typeof fetch;

describe("ActivityLogView", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("refreshes and clears both activity and error logs", async () => {
    render(<ActivityLogView />);

    await waitFor(() => expect(mockedServices.fetchActivityLog).toHaveBeenCalledTimes(1));

    await userEvent.click(screen.getByRole("button", { name: /refresh/i }));
    await waitFor(() => expect(mockedServices.fetchActivityLog).toHaveBeenCalledTimes(2));

    await userEvent.click(screen.getByRole("button", { name: /clear log/i }));
    await waitFor(() => expect(mockedServices.clearActivityLog).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("Activity log cleared"));

    await userEvent.click(screen.getByRole("button", { name: /error log/i }));
    await waitFor(() => expect(mockedServices.fetchErrors).toHaveBeenCalledTimes(1));

    await userEvent.click(screen.getByRole("button", { name: /refresh/i }));
    await waitFor(() => expect(mockedServices.fetchErrors).toHaveBeenCalledTimes(2));

    await userEvent.click(screen.getByRole("button", { name: /clear log/i }));
    await waitFor(() => expect(mockedServices.clearErrorLog).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("Error log cleared"));
  });

  it("shows errors when clearing or downloading fails", async () => {
    mockedServices.clearActivityLog.mockRejectedValueOnce(new Error("fail"));
    mockFetch.mockRejectedValueOnce(new Error("network"));

    render(<ActivityLogView />);

    await waitFor(() => expect(mockedServices.fetchActivityLog).toHaveBeenCalled());

    await userEvent.click(screen.getByRole("button", { name: /clear log/i }));
    await waitFor(() => expect(toastError).toHaveBeenCalledWith("Unable to clear log"));

    await userEvent.click(screen.getByRole("button", { name: /download/i }));
    await waitFor(() => expect(toastError).toHaveBeenCalledWith("Unable to download log"));
  });

  it("repopulates entries when switching tabs", async () => {
    mockedServices.fetchActivityLog.mockResolvedValueOnce(["activity a"]);
    mockedServices.fetchActivityLog.mockResolvedValueOnce(["activity b"]);
    mockedServices.fetchErrors.mockResolvedValueOnce(["error a"]);

    render(<ActivityLogView />);

    expect(await screen.findByText("activity a")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /error log/i }));
    expect(await screen.findByText("error a")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /activity log/i }));
    expect(await screen.findByText("activity b")).toBeInTheDocument();
  });
});
