import { afterEach, describe, expect, it, vi } from "vitest";
import { IncidentApi } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("IncidentApi event stream", () => {
  it("sends authentication and Last-Event-ID headers and ignores duplicate frames", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(
          'id: 8\nevent: tool.completed\ndata: {"investigation_id":"inv-1","sequence":8,"kind":"tool.completed","payload":{},"created_at":"2026-09-23T00:00:00Z"}\n\n',
        ));
        controller.close();
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(new Response(body, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const events: number[] = [];

    const latest = await new IncidentApi("secret-token").streamEvents(
      "inv-1",
      7,
      new AbortController().signal,
      (event) => events.push(event.sequence),
    );

    expect(latest).toBe(8);
    expect(events).toEqual([8]);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.headers).toMatchObject({
      Authorization: "Bearer secret-token",
      "Last-Event-ID": "7",
    });
    expect(fetchMock.mock.calls[0][0]).not.toContain("secret-token");
  });
});
