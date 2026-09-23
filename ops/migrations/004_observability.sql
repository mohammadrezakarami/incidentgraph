ALTER TABLE incidentgraph_app.investigations
    ADD COLUMN IF NOT EXISTS traceparent text;

ALTER TABLE incidentgraph_app.investigations
    DROP CONSTRAINT IF EXISTS investigations_traceparent_format;
ALTER TABLE incidentgraph_app.investigations
    ADD CONSTRAINT investigations_traceparent_format CHECK (
        traceparent IS NULL OR traceparent ~ '^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$'
    );

INSERT INTO incidentgraph_app.schema_migrations(version)
VALUES ('004_observability')
ON CONFLICT (version) DO NOTHING;
