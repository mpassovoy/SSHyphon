import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { VersionBanner } from "../components/VersionBanner";

describe("VersionBanner", () => {
  it("shows update available messaging", () => {
    render(
      <VersionBanner
        buildVersion="1.0.0"
        status="ready"
        onRetry={vi.fn()}
        info={{ version: "0.9.0", latest_version: "1.1.0", update_available: true, repository: "repo" }}
      />
    );

    expect(screen.getByText(/Update available: 1.1.0/)).toBeInTheDocument();
    expect(screen.getByText(/Runtime 0.9.0/)).toBeInTheDocument();
    expect(screen.getByText(/mismatch/)).toBeInTheDocument();
  });

  it("indicates matching versions", () => {
    render(
      <VersionBanner
        buildVersion="1.0.0"
        status="ready"
        onRetry={vi.fn()}
        info={{ version: "1.0.0", latest_version: "1.0.0", update_available: false, repository: "repo" }}
      />
    );

    expect(screen.getByText(/runtime verified/i)).toBeInTheDocument();
    expect(screen.getByText(/Latest release: 1.0.0/)).toBeInTheDocument();
  });
});
