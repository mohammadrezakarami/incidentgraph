import type {
  ApiFailure,
  DependencyView,
  EvidenceItem,
  Investigation,
  InvestigationEvent,
  InvestigationPage,
  ReplaySnapshot,
  ReportView,
  ServiceSummary,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code = "REQUEST_FAILED",
    readonly requestId: string | null = null,
    readonly retryable = false,
  ) {
    super(message);
  }
}

export class IncidentApi {
  constructor(
    private readonly token: string,
    private readonly baseUrl = "",
  ) {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${this.token}`,
        "Content-Type": "application/json",
        ...init.headers,
      },
    });
    if (!response.ok) {
      let failure: ApiFailure | null = null;
      try {
        failure = (await response.json()) as ApiFailure;
      } catch {
        // The fallback below deliberately avoids reflecting an untrusted response body.
      }
      throw new ApiError(
        failure?.error?.message ?? `Request failed with status ${response.status}`,
        response.status,
        failure?.error?.code,
        failure?.error?.request_id,
        failure?.error?.retryable,
      );
    }
    return (await response.json()) as T;
  }

  services() {
    return this.request<ServiceSummary[]>("/api/v1/services");
  }

  replaySnapshots() {
    return this.request<ReplaySnapshot[]>("/api/v1/replay-snapshots");
  }

  investigations(cursor?: string) {
    const suffix = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    return this.request<InvestigationPage>(`/api/v1/investigations${suffix}`);
  }

  investigation(id: string) {
    return this.request<Investigation>(`/api/v1/investigations/${encodeURIComponent(id)}`);
  }

  create(body: Record<string, unknown>, idempotencyKey: string) {
    return this.request<{ investigation_id: string; status: string; created_at: string }>(
      "/api/v1/investigations",
      { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(body) },
    );
  }

  report(id: string) {
    return this.request<ReportView>(`/api/v1/investigations/${encodeURIComponent(id)}/report`);
  }

  evidence(id: string, evidenceId: string) {
    return this.request<EvidenceItem>(
      `/api/v1/investigations/${encodeURIComponent(id)}/evidence/${encodeURIComponent(evidenceId)}`,
    );
  }

  dependencies(serviceId: string, cutoff: string) {
    const params = new URLSearchParams({ cutoff, direction: "both", depth: "2" });
    return this.request<DependencyView>(
      `/api/v1/services/${encodeURIComponent(serviceId)}/dependencies?${params}`,
    );
  }

  cancel(id: string) {
    return this.request(`/api/v1/investigations/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
    });
  }

  followUp(id: string, question: string, idempotencyKey: string) {
    return this.request(`/api/v1/investigations/${encodeURIComponent(id)}/followups`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ question, max_model_calls: 5, max_tool_calls: 8 }),
    });
  }

  review(id: string, reportVersion: number, decision: string, rationale: string) {
    return this.request(`/api/v1/investigations/${encodeURIComponent(id)}/reviews`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ report_version: reportVersion, decision, rationale }),
    });
  }

  async streamEvents(
    id: string,
    after: number,
    signal: AbortSignal,
    onEvent: (event: InvestigationEvent) => void,
  ): Promise<number> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/investigations/${encodeURIComponent(id)}/events`,
      {
        headers: {
          Authorization: `Bearer ${this.token}`,
          Accept: "text/event-stream",
          ...(after > 0 ? { "Last-Event-ID": String(after) } : {}),
        },
        signal,
      },
    );
    if (!response.ok || !response.body) {
      throw new ApiError("Event stream could not be opened", response.status, "STREAM_FAILED", null, true);
    }
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    let latest = after;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += value;
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        if (frame.startsWith(":")) continue;
        const lines = frame.split("\n");
        const idLine = lines.find((line) => line.startsWith("id:"));
        const dataLine = lines.find((line) => line.startsWith("data:"));
        if (!idLine || !dataLine) continue;
        const event = JSON.parse(dataLine.slice(5).trim()) as InvestigationEvent;
        const sequence = Number(idLine.slice(3).trim());
        if (Number.isFinite(sequence) && sequence > latest) {
          latest = sequence;
          onEvent(event);
        }
      }
    }
    return latest;
  }
}
