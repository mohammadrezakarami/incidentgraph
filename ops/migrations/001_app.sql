CREATE SCHEMA IF NOT EXISTS incidentgraph_app;
CREATE SCHEMA IF NOT EXISTS incidentgraph_checkpoints;

CREATE TABLE IF NOT EXISTS incidentgraph_app.schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incidentgraph_app.investigations (
    id uuid PRIMARY KEY,
    owner_id text NOT NULL,
    request_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    question text NOT NULL,
    target_service text NOT NULL,
    environment text NOT NULL,
    window_start timestamptz NOT NULL,
    window_end timestamptz NOT NULL,
    mode text NOT NULL CHECK (mode IN ('live', 'replay')),
    status text NOT NULL CHECK (
        status IN ('queued', 'running', 'waiting_for_review', 'completed',
                   'inconclusive', 'failed', 'cancelled')
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (owner_id, idempotency_key),
    CHECK (window_end > window_start)
);

CREATE TABLE IF NOT EXISTS incidentgraph_app.jobs (
    id bigserial PRIMARY KEY,
    investigation_id uuid NOT NULL UNIQUE
        REFERENCES incidentgraph_app.investigations(id) ON DELETE CASCADE,
    status text NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_owner text,
    lease_token uuid,
    leased_until timestamptz,
    heartbeat_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS jobs_claim_idx
    ON incidentgraph_app.jobs (status, available_at, leased_until, id);

CREATE TABLE IF NOT EXISTS incidentgraph_app.events (
    id bigserial PRIMARY KEY,
    investigation_id uuid NOT NULL
        REFERENCES incidentgraph_app.investigations(id) ON DELETE CASCADE,
    sequence bigint NOT NULL,
    kind text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (investigation_id, sequence)
);

CREATE INDEX IF NOT EXISTS events_investigation_idx
    ON incidentgraph_app.events (investigation_id, sequence);

INSERT INTO incidentgraph_app.schema_migrations(version)
VALUES ('001_app')
ON CONFLICT (version) DO NOTHING;
