ALTER TABLE incidentgraph_app.investigations
    ADD COLUMN IF NOT EXISTS thread_id uuid NOT NULL DEFAULT gen_random_uuid(),
    ADD COLUMN IF NOT EXISTS current_report_version integer NOT NULL DEFAULT 0
        CHECK (current_report_version >= 0),
    ADD COLUMN IF NOT EXISTS cancellation_requested_at timestamptz,
    ADD COLUMN IF NOT EXISTS cumulative_usage jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS investigations_thread_id_idx
    ON incidentgraph_app.investigations (thread_id);

ALTER TABLE incidentgraph_app.jobs
    DROP CONSTRAINT IF EXISTS jobs_status_check;
ALTER TABLE incidentgraph_app.jobs
    ADD CONSTRAINT jobs_status_check
    CHECK (status IN ('queued', 'running', 'waiting', 'completed', 'failed', 'cancelled'));
ALTER TABLE incidentgraph_app.jobs
    ADD COLUMN IF NOT EXISTS generation integer NOT NULL DEFAULT 1 CHECK (generation >= 1),
    ADD COLUMN IF NOT EXISTS task_kind text NOT NULL DEFAULT 'investigation'
        CHECK (task_kind IN ('investigation', 'review_resume', 'review_revision', 'follow_up')),
    ADD COLUMN IF NOT EXISTS target_report_version integer NOT NULL DEFAULT 1
        CHECK (target_report_version >= 1),
    ADD COLUMN IF NOT EXISTS input_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS budget jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE incidentgraph_app.events
    ADD COLUMN IF NOT EXISTS deduplication_key text;
CREATE UNIQUE INDEX IF NOT EXISTS events_deduplication_idx
    ON incidentgraph_app.events (investigation_id, deduplication_key)
    WHERE deduplication_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS incidentgraph_app.report_publications (
    investigation_id uuid NOT NULL
        REFERENCES incidentgraph_app.investigations(id) ON DELETE CASCADE,
    report_version integer NOT NULL CHECK (report_version >= 1),
    publication_key text NOT NULL,
    report_hash text NOT NULL CHECK (report_hash ~ '^[0-9a-f]{64}$'),
    outcome text NOT NULL CHECK (
        outcome IN ('probable_cause', 'inconclusive', 'no_incident_detected')
    ),
    published_by_attempt integer NOT NULL CHECK (published_by_attempt >= 1),
    lease_token uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (investigation_id, report_version),
    UNIQUE (investigation_id, publication_key)
);

CREATE TABLE IF NOT EXISTS incidentgraph_app.review_requests (
    id uuid PRIMARY KEY,
    investigation_id uuid NOT NULL
        REFERENCES incidentgraph_app.investigations(id) ON DELETE CASCADE,
    report_version integer NOT NULL CHECK (report_version >= 1),
    evidence_summary jsonb NOT NULL,
    uncertainties jsonb NOT NULL,
    allowed_decisions jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'accepted', 'rejected', 'revision_requested', 'expired')
    ),
    requested_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    decided_at timestamptz,
    reviewer_id text,
    UNIQUE (investigation_id, report_version),
    CHECK (expires_at > requested_at)
);

CREATE INDEX IF NOT EXISTS review_requests_pending_idx
    ON incidentgraph_app.review_requests (status, expires_at);

CREATE TABLE IF NOT EXISTS incidentgraph_app.review_decisions (
    id uuid PRIMARY KEY,
    review_request_id uuid NOT NULL
        REFERENCES incidentgraph_app.review_requests(id) ON DELETE CASCADE,
    investigation_id uuid NOT NULL
        REFERENCES incidentgraph_app.investigations(id) ON DELETE CASCADE,
    report_version integer NOT NULL CHECK (report_version >= 1),
    reviewer_id text NOT NULL,
    idempotency_key text NOT NULL,
    decision text NOT NULL CHECK (
        decision IN ('accept', 'reject', 'request_revision')
    ),
    rationale text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (reviewer_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS incidentgraph_app.follow_ups (
    id uuid PRIMARY KEY,
    investigation_id uuid NOT NULL
        REFERENCES incidentgraph_app.investigations(id) ON DELETE CASCADE,
    owner_id text NOT NULL,
    idempotency_key text NOT NULL,
    base_report_version integer NOT NULL CHECK (base_report_version >= 1),
    target_report_version integer NOT NULL CHECK (target_report_version >= 2),
    question text NOT NULL,
    budget jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (owner_id, idempotency_key),
    UNIQUE (investigation_id, target_report_version)
);

INSERT INTO incidentgraph_app.schema_migrations(version)
VALUES ('003_durability')
ON CONFLICT (version) DO NOTHING;
