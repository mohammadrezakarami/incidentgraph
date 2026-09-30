import type { Core } from "cytoscape";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, IncidentApi } from "./api";
import type {
  DependencyView,
  EvidenceItem,
  Investigation,
  InvestigationEvent,
  ReportView,
  ServiceSummary,
} from "./types";

const terminalStatuses = new Set(["completed", "inconclusive", "failed", "cancelled"]);

function formatTime(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(new Date(value));
}

function toLocalInput(date: Date) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function messageOf(error: unknown) {
  if (error instanceof ApiError) {
    return `${error.message}${error.requestId ? ` · request ${error.requestId}` : ""}`;
  }
  return error instanceof Error ? error.message : "Unexpected error";
}

function ModeBadge({ mode }: { mode: "live" | "replay" }) {
  return <span className={`mode mode-${mode}`}>{mode.toUpperCase()}</span>;
}

function StatusBadge({ status }: { status: Investigation["status"] }) {
  return <span className={`status status-${status}`}>{status.replaceAll("_", " ")}</span>;
}

function DependencyGraph({ view, highlighted }: { view: DependencyView; highlighted: Set<string> }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!host.current) return;
    const container = host.current;
    let graph: Core | null = null;
    let disposed = false;
    void import("cytoscape").then(({ default: cytoscape }) => {
      if (disposed) return;
      graph = cytoscape({
        container,
        elements: [
          ...view.services.map((service) => ({
            data: { id: service.service_id, label: service.name },
            classes: highlighted.has(service.service_id) ? "evidence" : "",
          })),
          ...view.edges.map((edge) => ({
            data: {
              id: `${edge.caller}-${edge.callee}`,
              source: edge.caller,
              target: edge.callee,
            },
          })),
        ],
        style: [
          {
            selector: "node",
            style: {
              label: "data(label)",
              color: "#d9e7ff",
              "font-size": 11,
              "text-valign": "bottom",
              "text-margin-y": 8,
              "background-color": "#46648f",
              width: 34,
              height: 34,
            },
          },
          {
            selector: "node.evidence",
            style: { "background-color": "#5eead4", color: "#bffdf4" },
          },
          {
            selector: "edge",
            style: {
              width: 2,
              "line-color": "#7894bd",
              "target-arrow-color": "#7894bd",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
            },
          },
        ],
        layout: { name: "breadthfirst", directed: true, padding: 24, spacingFactor: 1.25 },
        userZoomingEnabled: false,
        minZoom: 0.7,
        maxZoom: 1.4,
      });
    });
    return () => {
      disposed = true;
      graph?.destroy();
    };
  }, [highlighted, view]);
  return (
    <section className="panel dependency-panel" aria-labelledby="dependency-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Time-aware topology</p>
          <h2 id="dependency-title">Dependency view</h2>
        </div>
        <span className="muted">{view.direction} · depth {view.depth}</span>
      </div>
      <div ref={host} className="dependency-canvas" role="img" aria-label="Directed service dependency graph" />
      <div className="legend"><i /> cited service <span>→ caller depends on callee</span></div>
      <p className="fine-print">Topology valid at {formatTime(view.cutoff)}.</p>
    </section>
  );
}

function MetricChart({ evidence }: { evidence: EvidenceItem }) {
  const series = useMemo(() => {
    try {
      const content = JSON.parse(evidence.content ?? "{}") as {
        series?: { values?: [number | string, number | string][] }[];
      };
      return (content.series?.[0]?.values ?? [])
        .map(([time, value]) => [Number(time), Number(value)] as const)
        .filter(([time, value]) => Number.isFinite(time) && Number.isFinite(value));
    } catch {
      return [];
    }
  }, [evidence.content]);
  if (series.length < 2) return <p className="empty-small">No plottable metric series in this record.</p>;
  const values = series.map((point) => point[1]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = series
    .map(([, value], index) => `${(index / (series.length - 1)) * 100},${92 - ((value - min) / span) * 80}`)
    .join(" ");
  return (
    <figure className="metric-figure">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Metric values over the evidence window">
        <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
      <figcaption>{min.toPrecision(4)}–{max.toPrecision(4)} {evidence.unit ?? "recorded units"}</figcaption>
    </figure>
  );
}

function EvidenceDialog({ evidence, onClose }: { evidence: EvidenceItem; onClose: () => void }) {
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="evidence-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="panel-heading">
          <div>
            <p className="eyebrow">{evidence.kind} evidence</p>
            <h2 id="evidence-title">{evidence.source_id}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close evidence">×</button>
        </div>
        <dl className="metadata-grid">
          <div><dt>Observed</dt><dd>{formatTime(evidence.observed_at)}</dd></div>
          <div><dt>Freshness</dt><dd>{evidence.freshness_status}</dd></div>
          <div><dt>Services</dt><dd>{evidence.service_ids.join(", ")}</dd></div>
          <div><dt>Snapshot</dt><dd>{evidence.snapshot_id ?? "live"}</dd></div>
          <div className="metadata-wide"><dt>Provenance</dt><dd>{evidence.provenance_reference}</dd></div>
        </dl>
        {evidence.kind === "metric" && <MetricChart evidence={evidence} />}
        <h3>Recorded content</h3>
        <pre className="evidence-content">{evidence.content ?? "No content was retained."}</pre>
        {evidence.limitations.length > 0 && (
          <div className="notice"><strong>Limitations</strong><ul>{evidence.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
        )}
      </section>
    </div>
  );
}

function CitationButtons({ ids, open }: { ids: string[]; open: (id: string) => void }) {
  if (!ids.length) return null;
  return <span className="citations">{ids.map((id, index) => (
    <button key={id} onClick={() => open(id)} aria-label={`Open evidence ${id}`}>[{index + 1}]</button>
  ))}</span>;
}

function ReportPanel({ view, openEvidence }: { view: ReportView; openEvidence: (id: string) => void }) {
  const report = view.report;
  return (
    <section className="panel report-panel" aria-labelledby="report-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Report v{report.report_version} · {report.outcome.replaceAll("_", " ")}</p>
          <h2 id="report-title">Investigation report</h2>
        </div>
        <ModeBadge mode={report.mode} />
      </div>
      <p className="report-summary">{report.summary}</p>
      <p className="fine-print">Observation cutoff {formatTime(report.observation_cutoff)} · {report.snapshot_id ? `snapshot ${report.snapshot_id}` : "live observations"}</p>

      <h3>Ranked hypotheses</h3>
      {report.ranked_hypotheses.length ? report.ranked_hypotheses.map((hypothesis) => (
        <article className="hypothesis" key={hypothesis.rank}>
          <span className="rank">{hypothesis.rank}</span>
          <div>
            <div className="hypothesis-title"><strong>{hypothesis.mechanism}</strong><span>{hypothesis.evidence_strength} evidence</span></div>
            <p>{hypothesis.explanation_summary}</p>
            <div className="citation-row">Supports <CitationButtons ids={hypothesis.supporting_evidence_ids} open={openEvidence} /></div>
            {hypothesis.contradicting_evidence_ids.length > 0 && <div className="citation-row contradiction">Contradicts <CitationButtons ids={hypothesis.contradicting_evidence_ids} open={openEvidence} /></div>}
          </div>
        </article>
      )) : <p className="empty-small">No cause ranked. The system did not invent one.</p>}

      <div className="report-columns">
        <div>
          <h3>Observed impact</h3>
          {report.observed_impact.map((item, index) => <p key={index}>{item.description} <CitationButtons ids={item.evidence_ids} open={openEvidence} /></p>)}
          {!report.observed_impact.length && <p className="empty-small">No observed impact recorded.</p>}
        </div>
        <div>
          <h3>Limitations</h3>
          <ul>{report.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
          {!report.limitations.length && <p className="empty-small">No additional limitations recorded.</p>}
        </div>
      </div>

      <h3>Recommended next steps</h3>
      {report.recommended_next_steps.map((step, index) => (
        <article className="recommendation" key={index}>
          <div><strong>{step.description}</strong><span className={`risk risk-${step.risk_level}`}>{step.risk_level} risk</span></div>
          <p>{step.rationale} <CitationButtons ids={step.evidence_ids} open={openEvidence} /></p>
          {step.preconditions.length > 0 && <div><h4>Preconditions</h4><ul>{step.preconditions.map((item) => <li key={item}>{item}</li>)}</ul></div>}
          {step.verification_steps.length > 0 && <div><h4>Verification</h4><ul>{step.verification_steps.map((item) => <li key={item}>{item}</li>)}</ul></div>}
          {step.rollback_considerations.length > 0 && <div><h4>Rollback considerations</h4><ul>{step.rollback_considerations.map((item) => <li key={item}>{item}</li>)}</ul></div>}
          <small>Not executed by IncidentGraph.</small>
        </article>
      ))}
      {!report.recommended_next_steps.length && <p className="empty-small">No next steps proposed.</p>}
      <div className="report-footer"><span>Termination: {report.termination_reason}</span><span>Trace: {report.trace_reference}</span></div>
    </section>
  );
}

function EventTimeline({ events, state, onReconnect }: { events: InvestigationEvent[]; state: string; onReconnect: () => void }) {
  return (
    <section className="panel" aria-labelledby="timeline-title">
      <div className="panel-heading"><div><p className="eyebrow">Live execution</p><h2 id="timeline-title">Event timeline</h2></div><div className="stream-controls"><span className="stream-state"><i />{state}</span><button className="ghost" onClick={onReconnect}>Reconnect stream</button></div></div>
      {events.length ? <ol className="timeline">{events.map((event) => (
        <li key={event.sequence}>
          <time>{formatTime(event.created_at)}</time>
          <div>
            <strong>{String(event.payload.tool ?? event.kind.replaceAll(".", " · "))}</strong>
            <p>{String(event.payload.summary ?? event.payload.reason ?? event.payload.decision ?? `Event ${event.sequence}`)}</p>
            {(event.payload.duration_ms !== undefined || event.payload.outcome !== undefined) && (
              <small>
                {event.payload.outcome !== undefined ? String(event.payload.outcome) : ""}
                {event.payload.duration_ms !== undefined ? ` · ${Number(event.payload.duration_ms).toFixed(1)} ms` : ""}
              </small>
            )}
          </div>
        </li>
      ))}</ol> : <p className="empty-small">Waiting for the first persisted event…</p>}
    </section>
  );
}

function CreateForm({ services, onCreate, busy }: { services: ServiceSummary[]; onCreate: (body: Record<string, unknown>) => Promise<void>; busy: boolean }) {
  const end = useMemo(() => new Date(), []);
  const [service, setService] = useState("");
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"live" | "replay">("replay");
  const [start, setStart] = useState(toLocalInput(new Date(end.getTime() - 10 * 60_000)));
  const [finish, setFinish] = useState(toLocalInput(end));
  useEffect(() => { if (!service && services[0]) setService(services[0].service_id); }, [service, services]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    await onCreate({
      question,
      target_service: service,
      environment: "lab",
      window_start: new Date(start).toISOString(),
      window_end: new Date(finish).toISOString(),
      mode,
    });
  }
  return (
    <section className="panel create-panel" aria-labelledby="new-title">
      <div><p className="eyebrow">Bounded, read-only investigation</p><h2 id="new-title">Start a run</h2></div>
      <form onSubmit={submit}>
        <label>Service<select value={service} onChange={(event) => setService(event.target.value)} required>{services.map((item) => <option value={item.service_id} key={item.service_id}>{item.name}</option>)}</select></label>
        <label className="wide">Incident question<textarea value={question} onChange={(event) => setQuestion(event.target.value)} minLength={8} maxLength={2000} placeholder="What changed in checkout latency during this window?" required /></label>
        <fieldset className="mode-picker"><legend>Observation mode</legend><label><input type="radio" name="mode" value="replay" checked={mode === "replay"} onChange={() => setMode("replay")} /><span><b>REPLAY</b>Immutable snapshot at cutoff</span></label><label><input type="radio" name="mode" value="live" checked={mode === "live"} onChange={() => setMode("live")} /><span><b>LIVE</b>Running lab observations</span></label></fieldset>
        <label>Window start<input type="datetime-local" value={start} onChange={(event) => setStart(event.target.value)} required /></label>
        <label>Window end<input type="datetime-local" value={finish} onChange={(event) => setFinish(event.target.value)} required /></label>
        <button className="primary" disabled={busy || !services.length}>{busy ? "Queueing…" : "Start investigation"}</button>
      </form>
    </section>
  );
}

function AuthScreen({ onConnect }: { onConnect: (token: string, keep: boolean) => void }) {
  const [token, setToken] = useState("");
  const [keep, setKeep] = useState(false);
  return <main className="auth-shell"><section className="auth-card"><div className="brand-mark">IG</div><p className="eyebrow">Local incident intelligence</p><h1>IncidentGraph</h1><p>Connect to the loopback API with a development token. The token is never placed in the URL.</p><form onSubmit={(event) => { event.preventDefault(); onConnect(token.trim(), keep); }}><label>Bearer token<input type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} required /></label><label className="check"><input type="checkbox" checked={keep} onChange={(event) => setKeep(event.target.checked)} />Keep only for this browser tab</label><button className="primary">Open console</button></form></section></main>;
}

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("incidentgraph-token") ?? "");
  const [services, setServices] = useState<ServiceSummary[]>([]);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedId, setSelectedId] = useState(() => new URLSearchParams(location.search).get("investigation"));
  const [selected, setSelected] = useState<Investigation | null>(null);
  const [events, setEvents] = useState<InvestigationEvent[]>([]);
  const [report, setReport] = useState<ReportView | null>(null);
  const [dependency, setDependency] = useState<DependencyView | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem | null>(null);
  const [citedServices, setCitedServices] = useState<Set<string>>(new Set());
  const [streamState, setStreamState] = useState("idle");
  const [streamEpoch, setStreamEpoch] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [followUp, setFollowUp] = useState("");
  const [reviewRationale, setReviewRationale] = useState("");
  const api = useMemo(() => token ? new IncidentApi(token) : null, [token]);
  const activeContext = useRef({ api, selectedId });
  activeContext.current = { api, selectedId };

  const refreshList = useCallback(async () => {
    if (!api) return;
    const page = await api.investigations();
    if (activeContext.current.api === api) setInvestigations(page.items);
  }, [api]);

  const refreshSelected = useCallback(async () => {
    if (!api || !selectedId) return;
    const current = await api.investigation(selectedId);
    const [graph, currentReport] = await Promise.all([
      api.dependencies(current.target_service, current.window_end),
      current.current_report_version > 0 ? api.report(selectedId) : Promise.resolve(null),
    ]);
    if (activeContext.current.api !== api || activeContext.current.selectedId !== selectedId) return;
    setSelected(current);
    setDependency(graph);
    setReport(currentReport);
    return current;
  }, [api, selectedId]);

  useEffect(() => {
    if (!api) return;
    let active = true;
    setError("");
    Promise.all([api.services(), api.investigations()])
      .then(([catalog, page]) => { if (active) { setServices(catalog); setInvestigations(page.items); } })
      .catch((failure) => { if (active) setError(messageOf(failure)); });
    return () => { active = false; };
  }, [api]);

  useEffect(() => {
    if (!api || !selectedId || !report) {
      setCitedServices(new Set());
      return;
    }
    const reportValue = report.report;
    const ids = new Set<string>();
    reportValue.ranked_hypotheses.forEach((item) => {
      item.supporting_evidence_ids.forEach((id) => ids.add(id));
      item.contradicting_evidence_ids.forEach((id) => ids.add(id));
    });
    [
      ...reportValue.observed_symptoms,
      ...reportValue.observed_impact,
      ...reportValue.potential_impact,
      ...reportValue.recommended_next_steps,
    ].forEach((item) => item.evidence_ids.forEach((id) => ids.add(id)));
    let active = true;
    void Promise.allSettled([...ids].map((id) => api.evidence(selectedId, id))).then(
      (results) => {
        if (!active) return;
        const services = new Set<string>();
        results.forEach((result) => {
          if (result.status === "fulfilled") {
            result.value.service_ids.forEach((serviceId) => services.add(serviceId));
          }
        });
        setCitedServices(services);
      },
    );
    return () => { active = false; };
  }, [api, report, selectedId]);

  useEffect(() => {
    setSelected(null);
    setEvents([]);
    setReport(null);
    setDependency(null);
    setEvidence(null);
    setFollowUp("");
    setReviewRationale("");
    if (!selectedId) return;
    const url = new URL(location.href);
    url.searchParams.set("investigation", selectedId);
    history.replaceState(null, "", url);
    let active = true;
    refreshSelected().catch((failure) => { if (active) setError(messageOf(failure)); });
    return () => { active = false; };
  }, [refreshSelected, selectedId]);

  useEffect(() => {
    if (!api || !selectedId || !selected || selected.investigation_id !== selectedId) {
      setStreamState(selectedId ? "loading" : "idle");
      return;
    }
    const streamApi = api;
    const streamInvestigationId = selectedId;
    const controller = new AbortController();
    let active = true;
    let lastSequence = events.at(-1)?.sequence ?? 0;
    async function connect() {
      let retry = 0;
      while (active && !controller.signal.aborted) {
        try {
          setStreamState(retry ? "reconnecting" : "connected");
          lastSequence = await streamApi.streamEvents(streamInvestigationId, lastSequence, controller.signal, (event) => {
            if (!active) return;
            setEvents((prior) => prior.some((item) => item.sequence === event.sequence) ? prior : [...prior, event]);
          });
          if (!active) return;
          const [current] = await Promise.all([refreshSelected(), refreshList()]);
          if (!active) return;
          if (current && terminalStatuses.has(current.status)) {
            setStreamState("complete");
            return;
          }
          retry += 1;
        } catch (failure) {
          if (controller.signal.aborted) return;
          retry += 1;
          setStreamState("reconnecting");
          if (retry >= 5) { setError(messageOf(failure)); setStreamState("disconnected"); return; }
        }
        await new Promise((resolve) => setTimeout(resolve, Math.min(1000 * 2 ** retry, 8000)));
      }
    }
    void connect();
    return () => { active = false; controller.abort(); };
    // Events are appended inside the stream; reconnect position is held within this effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, refreshList, refreshSelected, selected?.status, selectedId, streamEpoch]);

  function connect(value: string, keep: boolean) {
    if (keep) sessionStorage.setItem("incidentgraph-token", value);
    else sessionStorage.removeItem("incidentgraph-token");
    setToken(value);
  }

  function disconnect() {
    activeContext.current = { api: null, selectedId: null };
    sessionStorage.removeItem("incidentgraph-token");
    setToken("");
    setSelectedId(null);
    setSelected(null);
    setInvestigations([]);
    setServices([]);
    setReport(null);
    setEvents([]);
    setDependency(null);
    setEvidence(null);
    setError("");
    history.replaceState(null, "", location.pathname);
  }

  async function action(operation: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await operation(); await Promise.all([refreshSelected(), refreshList()]); }
    catch (failure) { setError(messageOf(failure)); }
    finally { setBusy(false); }
  }

  async function create(body: Record<string, unknown>) {
    if (!api) return;
    await action(async () => {
      const accepted = await api.create(body, crypto.randomUUID());
      setSelectedId(accepted.investigation_id);
    });
  }

  async function openEvidence(id: string) {
    if (!api || !selectedId) return;
    try {
      const item = await api.evidence(selectedId, id);
      if (activeContext.current.api === api && activeContext.current.selectedId === selectedId) setEvidence(item);
    }
    catch (failure) { setError(messageOf(failure)); }
  }

  if (!token) return <AuthScreen onConnect={connect} />;

  return (
    <div className="app-shell">
      <header className="topbar"><div className="brand"><div className="brand-mark">IG</div><div><strong>IncidentGraph</strong><span>Evidence-grounded console</span></div></div><div className="top-actions"><span className="local-only">● LOCAL ONLY</span><button className="ghost" onClick={disconnect}>Disconnect</button></div></header>
      {error && <div className="error-banner" role="alert"><strong>Request failed</strong><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error">×</button></div>}
      <div className="workspace">
        <aside className="sidebar">
          <div className="sidebar-heading"><div><p className="eyebrow">History</p><h2>Investigations</h2></div><button className="icon-button" aria-label="Refresh investigations" onClick={() => refreshList().catch((failure) => setError(messageOf(failure)))}>↻</button></div>
          <nav aria-label="Investigations"><ul className="investigation-list">{investigations.map((item) => <li key={item.investigation_id}><button className={selectedId === item.investigation_id ? "selected" : ""} onClick={() => setSelectedId(item.investigation_id)}><span><ModeBadge mode={item.mode} /><StatusBadge status={item.status} /></span><strong>{item.question}</strong><small>{item.target_service} · {formatTime(item.created_at)}</small></button></li>)}</ul></nav>
          {!investigations.length && <p className="empty-small">No investigations for this user.</p>}
        </aside>
        <main className="content">
          {!selected && <CreateForm services={services} onCreate={create} busy={busy} />}
          {selected && <>
            <section className="run-header"><button className="back-link" onClick={() => { setSelectedId(null); history.replaceState(null, "", location.pathname); }}>← New run</button><div className="run-title"><div><span className="eyebrow">{selected.target_service} · {selected.environment}</span><h1>{selected.question}</h1></div><div className="run-badges"><ModeBadge mode={selected.mode} /><StatusBadge status={selected.status} /></div></div><div className="window-line"><span>{formatTime(selected.window_start)} → {formatTime(selected.window_end)}</span><span>Owner {selected.owner_id}</span><span>Request {selected.request_id.slice(0, 8)}</span></div><div className="run-actions">{!terminalStatuses.has(selected.status) && <button className="danger-outline" disabled={busy} onClick={() => api && action(() => api.cancel(selected.investigation_id))}>Cancel run</button>}<button className="ghost" onClick={() => refreshSelected().catch((failure) => setError(messageOf(failure)))}>Refresh</button></div></section>
            <div className="dashboard-grid">
              <EventTimeline events={events} state={streamState} onReconnect={() => setStreamEpoch((value) => value + 1)} />
              {dependency && <DependencyGraph view={dependency} highlighted={citedServices} />}
              {report ? <ReportPanel view={report} openEvidence={openEvidence} /> : <section className="panel report-panel"><p className="eyebrow">Partial result</p><h2>Report pending</h2><p className="muted">Persisted events remain visible while the bounded investigator is working.</p></section>}
              {report?.review?.status === "pending" && <section className="panel action-panel"><p className="eyebrow">Human decision required</p><h2>Review report v{report.report.report_version}</h2><div className="warning">Accepting this report authorizes publication only. It does not run commands, change infrastructure, or execute recommendations.</div><label>Decision rationale<textarea value={reviewRationale} onChange={(event) => setReviewRationale(event.target.value)} minLength={3} /></label><div className="button-row"><button className="primary" disabled={busy || reviewRationale.length < 3} onClick={() => api && action(() => api.review(selected.investigation_id, report.report.report_version, "accept", reviewRationale))}>Accept report</button><button className="ghost" disabled={busy || reviewRationale.length < 3} onClick={() => api && action(() => api.review(selected.investigation_id, report.report.report_version, "request_revision", reviewRationale))}>Request revision</button><button className="danger-outline" disabled={busy || reviewRationale.length < 3} onClick={() => api && action(() => api.review(selected.investigation_id, report.report.report_version, "reject", reviewRationale))}>Reject</button></div></section>}
              {report && terminalStatuses.has(selected.status) && <section className="panel action-panel"><p className="eyebrow">Versioned continuation</p><h2>Ask a follow-up</h2><p className="muted">Uses the authorized context and an explicit incremental budget. The existing report remains immutable.</p><label>Follow-up question<textarea value={followUp} onChange={(event) => setFollowUp(event.target.value)} minLength={8} /></label><button className="primary" disabled={busy || followUp.length < 8} onClick={() => api && action(async () => { await api.followUp(selected.investigation_id, followUp, crypto.randomUUID()); setFollowUp(""); })}>Queue follow-up</button></section>}
            </div>
          </>}
        </main>
      </div>
      {evidence && <EvidenceDialog evidence={evidence} onClose={() => setEvidence(null)} />}
    </div>
  );
}
