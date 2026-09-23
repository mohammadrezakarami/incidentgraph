export type InvestigationStatus =
  | "queued"
  | "running"
  | "waiting_for_review"
  | "completed"
  | "inconclusive"
  | "failed"
  | "cancelled";

export interface ServiceSummary {
  service_id: string;
  name: string;
  aliases: string[];
  environment: string;
  owner: string;
  metadata_version: string;
}

export interface Investigation {
  investigation_id: string;
  owner_id: string;
  request_id: string;
  question: string;
  target_service: string;
  environment: string;
  window_start: string;
  window_end: string;
  mode: "live" | "replay";
  status: InvestigationStatus;
  created_at: string;
  updated_at: string;
  current_report_version: number;
}

export interface InvestigationPage {
  items: Investigation[];
  next_cursor: string | null;
}

export interface InvestigationEvent {
  investigation_id: string;
  sequence: number;
  kind: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface EvidenceItem {
  evidence_id: string;
  kind: "document" | "metric" | "log" | "topology" | "change" | "reviewed_incident";
  source_id: string;
  source_version: string;
  service_ids: string[];
  environment: string;
  observed_at: string;
  collected_at: string;
  content_hash: string;
  freshness_status: "fresh" | "stale" | "unknown";
  limitations: string[];
  provenance_reference: string;
  window_start: string | null;
  window_end: string | null;
  valid_from: string | null;
  valid_to: string | null;
  snapshot_id: string | null;
  query_template_id: string | null;
  safe_parameters: Record<string, unknown>;
  content: string | null;
  unit: string | null;
  aggregation: string | null;
}

export interface CitationBlock {
  description?: string;
  rationale?: string;
  evidence_ids: string[];
}

export interface Hypothesis {
  rank: number;
  mechanism: string;
  suspected_component: string;
  evidence_strength: "low" | "medium" | "high";
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  explanation_summary: string;
  additional_evidence_needed: string[];
}

export interface InvestigationReport {
  investigation_id: string;
  report_version: number;
  mode: "live" | "replay";
  snapshot_id: string | null;
  target_service: string;
  environment: string;
  incident_window: { start: string; end: string };
  observation_cutoff: string;
  outcome: "probable_cause" | "inconclusive" | "no_incident_detected";
  summary: string;
  observed_symptoms: CitationBlock[];
  ranked_hypotheses: Hypothesis[];
  observed_impact: CitationBlock[];
  potential_impact: CitationBlock[];
  recommended_next_steps: (CitationBlock & {
    risk_level: "low" | "medium" | "high";
    preconditions: string[];
    verification_steps: string[];
    rollback_considerations: string[];
    execution_status: "not_executed";
  })[];
  limitations: string[];
  review_status: string;
  termination_reason: string;
  usage_and_timing: Record<string, number | boolean>;
  trace_reference: string;
}

export interface ReviewRecord {
  review_id: string;
  investigation_id: string;
  report_version: number;
  status: "pending" | "accepted" | "rejected" | "revision_requested" | "expired";
  reviewer_id: string | null;
  requested_at: string;
  expires_at: string;
  decided_at: string | null;
}

export interface ReportView {
  report: InvestigationReport;
  review: ReviewRecord | null;
}

export interface DependencyView {
  service_id: string;
  cutoff: string;
  direction: "inbound" | "outbound" | "both";
  depth: number;
  services: ServiceSummary[];
  edges: { caller: string; callee: string; relationship: "DEPENDS_ON" }[];
}

export interface ApiFailure {
  error: { code: string; message: string; request_id: string | null; retryable: boolean };
}
