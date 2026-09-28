# IncidentGraph release and operations runbook

This runbook covers the local-first 0.1.0 release. It does not authorize publishing, cloud
deployment, public endpoints, or a new model evaluation. All host ports remain bound to loopback.
No paid service is required for setup, deterministic replay, or the committed evaluation report.

## Clean-clone verification

The first setup is online because it downloads pinned Python/Node dependencies, container images,
and a Chromium binary. The optional embedding model is downloaded only by ingestion/retrieval
commands. A fresh clone is prepared with:

```bash
git clone https://github.com/mohammadrezakarami/incidentgraph.git
cd incidentgraph
./bootstrap.sh
.venv/bin/python scripts/create_local_env.py
cd frontend && npx playwright install chromium && cd ..
make doctor
make up
make migrate
make smoke
make demo
make release-verify
```

`create_local_env.py` writes a mode-0600 ignored `.env` and prints a one-time bearer token. Store
that token outside Git. `make demo` is a headless, deterministic browser demonstration against the
real FastAPI/PostgreSQL lifecycle and a clearly labelled fixture publisher; it makes no model call
and is not an AI-quality benchmark. Stop the retained core services with `make down`.

The recorded Phase 10 verification must use a separate Compose project, for example
`COMPOSE_PROJECT=incidentgraph-phase10-verify`, so its named volumes cannot reuse development data.
The verification report and exact revision belong in `docs/progress/phase-10-report.md`.

## Release configuration

`Dockerfile` builds the common non-root backend image used by the API and worker. The private
evaluator directory is excluded by `.dockerignore`; the image contains only operational config,
migrations, corpus data, and agent-readable captures. Build and start the API with:

```bash
make release-build
make release-up
```

The source checkout remains the simplest frontend release: `make test-frontend` creates the frozen
production bundle and `npm --prefix frontend run preview` serves it on loopback. The investigator
worker is intentionally not part of the default release profile: enable it only after configuring
an approved local provider, starting the local model profile, and verifying the zero-dollar cost
ceiling. API and worker use the same `incidentgraph-core:0.1.0` image.

`release-build` installs the locked ML dependency stack and can be resource-intensive. It is a
remote-CI task by default on a small laptop; it does not run a model. The deterministic local gate
does not require rebuilding the image.

## Resource profiles

The standard core profile caps the two PostgreSQL services plus Neo4j at about 2.8 GiB and four
CPUs in aggregate. The low profile reduces those caps to about 1.9 GiB and 2.25 CPUs:

```bash
make up RESOURCE_PROFILE=low
make lab-up RESOURCE_PROFILE=low
```

The full lab adds three bounded services, Redis, and Prometheus. The optional Ollama profile adds a
separate 4 GiB/8 CPU ceiling and is never started by `make up`, `make demo`, or tests. The release
API is capped at 768 MiB/1.5 CPUs; the optional worker is capped at 1.5 GiB/2 CPUs. Compose limits
are ceilings, not measured steady-state requirements.

## Offline deterministic replay

After `./bootstrap.sh` has completed once, this command runs without uv/npm installation or model
downloads:

```bash
make test-offline
make evaluate-test
make report
```

`make test-offline` invokes the existing virtual environment and `node_modules` directly, forces
Hugging Face/Transformers offline mode, and runs backend unit tests, frontend tests, and the
production frontend build. `make evaluate-test` verifies the current v4 freeze and reproduces the
committed v4 pass summary from 120 per-job records; it does not call an LLM. Offline service replay
also requires the digest-pinned Docker images and Chromium to be present in the local caches. The
project does not claim offline first-time installation.

## Backup and restore

PostgreSQL is the durable application source of investigations, events, reviews, jobs, and
checkpoints. Create a non-overwriting custom-format dump and checksum sidecar while `app-db` is
healthy:

```bash
make backup-app BACKUP=backups/incidentgraph-app-2026-09-28.dump
```

Stop the API and worker before restore, keep `app-db` running, and use the exact destructive
confirmation phrase. Restore validates the sidecar checksum and archive directory before applying
`pg_restore --clean --if-exists`:

```bash
make restore-app \
  BACKUP=backups/incidentgraph-app-2026-09-28.dump \
  CONFIRM=RESTORE_INCIDENTGRAPH_APP_DB
make smoke
```

The lab database contains disposable workload state and is rebuilt by `make lab-up`. Neo4j is a
derived projection of the reviewed `config/topology.json` and `data/corpus` sources; restore it by
starting an empty named volume, then running `make seed`, `make ingest`, and
`make verify-ingestion`. This avoids unsupported hot-copy semantics in Community Edition.

Normal teardown never removes volumes. The separate reset target prints the exact volume names and
requires `CONFIRM=DELETE_INCIDENTGRAPH_VOLUMES`; take an application backup first.

## Safe shutdown

1. Stop accepting new work and let the active worker finish its current lease.
2. Send Ctrl-C to host `make api`, `make worker`, and `make frontend` processes. The worker handles
   SIGINT/SIGTERM, finishes its active attempt, closes PostgreSQL, and then exits.
3. Run `make release-down` for the image profile or `make down` for source mode.
4. Do not add `--volumes`; named database volumes are intentionally retained.

API shutdown closes its database pool. A worker killed beyond the 210-second Compose grace period
may leave a leased job, which is recovered through the existing lease-expiry/fencing semantics.

## Troubleshooting

- **`doctor` reports `CHANGE_ME` or no principal:** remove an incomplete `.env` and rerun
  `.venv/bin/python scripts/create_local_env.py`; use `--force` only when replacement is intended.
- **Port already allocated:** stop the other process using 55432, 55433, 57474, 57687, 8000, or
  5173. Do not change only the DSN or only the Compose port; those values are a contract.
- **Docker daemon unavailable:** start Docker Desktop, then rerun `make up`. Client availability
  alone is not enough.
- **Neo4j becomes unhealthy in the low profile:** use `RESOURCE_PROFILE=standard`; the low profile
  is intended for deterministic replay, not concurrent ingestion and full-lab capture.
- **Playwright cannot find Chromium:** run `cd frontend && npx playwright install chromium` while
  online, then retry `make demo`.
- **`test-offline` attempts a download:** dependencies were not fully bootstrapped or the local
  caches were removed. Reconnect once, run `./bootstrap.sh`, and retry offline.
- **New investigation returns a configuration error:** the default provider is deliberately
  disabled. Existing records and deterministic replay remain available; no fake model is used.
- **Release verification fails:** read the named failed check. Never bypass missing lockfiles,
  unpinned images, evaluator leakage, a tracked `.env`, or failed frozen evaluation evidence.

## CI and security scope

Normal GitHub CI uses frozen installs and separates deterministic checks from the service/browser
job. The security workflow runs Gitleaks plus Trivy repository, dependency, configuration, and
container scans. These tools reduce known-risk exposure but do not prove security. The manually
triggered model-evaluation guard only verifies sealed evidence and never accesses provider secrets.
GitHub-hosted execution may consume the account's included Actions minutes; every gate also has a
local command and no paid third-party service is required.

## Known limitations

- The incident corpus and evaluation are project-authored laboratory data, not production evidence.
- The Phase 9 semantic review is AI-assisted, not independent human validation; 20 reports cover
  seven independent capture groups.
- The default release can view/replay persisted records but cannot start a model investigation
  until an explicitly approved local provider is configured.
- There is one worker and no high-availability or multi-tenant claim.
- The low resource profile is a constrained replay profile, not a capacity benchmark.
- Cloud deployment, public exposure, CI publication, tags, and GitHub Releases remain unauthorized.
- Repository-wide Ruff formatting predates the v4 source freeze. CI format-checks the Phase 10
  release paths and lints the whole repository; frozen evaluation files are not mechanically
  reformatted because that would invalidate their hashes.
