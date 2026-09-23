import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("cytoscape", () => ({
  default: vi.fn(() => ({ destroy: vi.fn() })),
}));

const record = {
  investigation_id: "11111111-1111-4111-8111-111111111111",
  owner_id: "api-owner",
  request_id: "22222222-2222-4222-8222-222222222222",
  question: "Why did the API-reported checkout latency increase?",
  target_service: "svc-checkout",
  environment: "lab",
  window_start: "2026-09-23T10:00:00Z",
  window_end: "2026-09-23T10:10:00Z",
  mode: "replay",
  status: "completed",
  created_at: "2026-09-23T10:11:00Z",
  updated_at: "2026-09-23T10:12:00Z",
  current_report_version: 0,
};

function json(value: unknown) {
  return Promise.resolve(new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  }));
}

beforeEach(() => {
  sessionStorage.clear();
  history.replaceState(null, "", "/");
});

afterEach(() => vi.unstubAllGlobals());

describe("IncidentGraph console", () => {
  it("keeps a default token out of browser storage and URLs", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path.endsWith("/api/v1/services")) return json([]);
      return json({ items: [], next_cursor: null });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.change(screen.getByLabelText("Bearer token"), { target: { value: "tab-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Open console" }));

    await screen.findByText("Investigations");
    expect(sessionStorage.getItem("incidentgraph-token")).toBeNull();
    expect(location.href).not.toContain("tab-secret");
  });

  it("renders investigation facts supplied by the API", async () => {
    sessionStorage.setItem("incidentgraph-token", "viewer-token");
    const fetchMock = vi.fn((path: string) => {
      if (path.endsWith("/api/v1/services")) {
        return json([{ service_id: "svc-checkout", name: "checkout", aliases: [], environment: "lab", owner: "commerce", metadata_version: "1" }]);
      }
      if (path.includes("/dependencies")) {
        return json({ service_id: "svc-checkout", cutoff: record.window_end, direction: "both", depth: 2, services: [], edges: [] });
      }
      if (path.endsWith(record.investigation_id)) return json(record);
      return json({ items: [record], next_cursor: null });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    const historyItem = await screen.findByRole("button", { name: /Why did the API-reported/ });
    fireEvent.click(historyItem);

    await waitFor(() => expect(screen.getByRole("heading", { name: record.question })).toBeVisible());
    expect(screen.getByText("Owner api-owner")).toBeVisible();
    expect(screen.getAllByText("REPLAY").length).toBeGreaterThan(0);
    expect(screen.getByText("Report pending")).toBeVisible();
  });
});
