CREATE SCHEMA IF NOT EXISTS lab;

CREATE TABLE IF NOT EXISTS lab.schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lab.orders (
    order_id text PRIMARY KEY,
    amount_cents integer NOT NULL CHECK (amount_cents BETWEEN 100 AND 100000),
    status text NOT NULL CHECK (status IN ('processing', 'completed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS orders_updated_at_idx ON lab.orders (updated_at);

INSERT INTO lab.schema_migrations(version)
VALUES ('002_lab')
ON CONFLICT (version) DO NOTHING;
