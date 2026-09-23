CREATE TABLE IF NOT EXISTS incidentgraph_app.evidence (
    investigation_id uuid NOT NULL
        REFERENCES incidentgraph_app.investigations(id) ON DELETE CASCADE,
    evidence_id uuid NOT NULL,
    content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (investigation_id, evidence_id)
);

CREATE INDEX IF NOT EXISTS evidence_investigation_created_idx
    ON incidentgraph_app.evidence (investigation_id, created_at, evidence_id);

CREATE TABLE IF NOT EXISTS incidentgraph_app.reports (
    investigation_id uuid NOT NULL
        REFERENCES incidentgraph_app.investigations(id) ON DELETE CASCADE,
    report_version integer NOT NULL CHECK (report_version >= 1),
    outcome text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (investigation_id, report_version)
);

ALTER TABLE incidentgraph_app.reports
    DROP CONSTRAINT IF EXISTS reports_outcome_check;
ALTER TABLE incidentgraph_app.reports
    ADD CONSTRAINT reports_outcome_check
    CHECK (outcome IN ('probable_cause', 'inconclusive', 'no_incident_detected'));

INSERT INTO incidentgraph_app.schema_migrations(version)
VALUES ('002_agent')
ON CONFLICT (version) DO NOTHING;
