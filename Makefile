UV := UV_PYTHON_INSTALL_DIR='$(CURDIR)/.tools/python' UV_CACHE_DIR='$(CURDIR)/.tools/cache' .tools/uv
COMPOSE := docker compose -f ops/compose.yaml --env-file .env

.PHONY: doctor bootstrap up down migrate seed ingest verify-ingestion benchmark-embeddings smoke lab-up lab-migrate lab-ready scenario capture-suite verify-captures test coverage test-integration test-lab-integration test-graph-integration lint typecheck

doctor:
	$(UV) run incidentgraph doctor

bootstrap:
	$(UV) sync --frozen --dev

up:
	$(COMPOSE) up -d --wait app-db lab-db neo4j

down:
	$(COMPOSE) down

migrate:
	$(UV) run incidentgraph migrate

seed:
	$(UV) run incidentgraph-ingest seed

ingest:
	$(UV) run incidentgraph-ingest ingest

verify-ingestion:
	$(UV) run incidentgraph-ingest verify

benchmark-embeddings:
	$(UV) run incidentgraph-ingest benchmark

smoke:
	$(UV) run incidentgraph check-connections

lab-up:
	mkdir -p data/runtime/lab-logs data/runtime/lab-traces data/captures data/evaluator
	$(COMPOSE) up -d --wait app-db lab-db neo4j redis prometheus gateway checkout payments
	$(UV) run incidentgraph-lab migrate
	$(UV) run incidentgraph-lab wait-ready

lab-migrate:
	$(UV) run incidentgraph-lab migrate

lab-ready:
	$(UV) run incidentgraph-lab wait-ready

scenario:
	$(UV) run incidentgraph-lab scenario --scenario "$(SCENARIO)"

capture-suite:
	$(UV) run incidentgraph-lab capture-suite

verify-captures:
	$(UV) run incidentgraph-lab verify-captures

test:
	$(UV) run pytest -m "not integration"

coverage:
	$(UV) run pytest -m "not integration" --cov --cov-report=term-missing

test-integration:
	RUN_INTEGRATION=1 $(UV) run pytest -m "integration and not lab_integration and not graph_integration" -v

test-lab-integration:
	RUN_LAB_INTEGRATION=1 $(UV) run pytest -m lab_integration -v

test-graph-integration:
	RUN_GRAPH_INTEGRATION=1 $(UV) run pytest -m graph_integration -v

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run mypy
