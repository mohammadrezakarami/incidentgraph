UV := UV_PYTHON_INSTALL_DIR='$(CURDIR)/.tools/python' UV_CACHE_DIR='$(CURDIR)/.tools/cache' .tools/uv
COMPOSE := docker compose -f ops/compose.yaml --env-file .env

.PHONY: doctor bootstrap up down migrate retention-status seed ingest verify-ingestion benchmark-embeddings retrieve evaluate-retrieval-dev verify-retrieval build-incident-eval verify-incident-eval investigator-status setup-checkpointer model-up model-pull phase5-real-gate smoke lab-up lab-migrate lab-ready scenario capture-suite verify-captures api worker frontend test test-frontend test-e2e coverage test-integration test-phase6-integration test-lab-integration test-graph-integration test-retrieval-integration test-investigator-integration lint typecheck

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

retention-status:
	$(UV) run incidentgraph retention

seed:
	$(UV) run incidentgraph-ingest seed

ingest:
	$(UV) run incidentgraph-ingest ingest

verify-ingestion:
	$(UV) run incidentgraph-ingest verify

benchmark-embeddings:
	$(UV) run incidentgraph-ingest benchmark

retrieve:
	$(UV) run incidentgraph-retrieval search --variant "$(VARIANT)" --query "$(QUERY)" --service "$(SERVICE)" --authorize svc-gateway --authorize svc-checkout --authorize svc-payments

evaluate-retrieval-dev:
	$(UV) run incidentgraph-retrieval evaluate-dev

verify-retrieval:
	$(UV) run incidentgraph-retrieval verify

build-incident-eval:
	$(UV) run incidentgraph-incident-eval build

verify-incident-eval:
	$(UV) run incidentgraph-incident-eval verify

investigator-status:
	$(UV) run incidentgraph-investigator status

setup-checkpointer:
	$(UV) run incidentgraph-investigator setup-checkpointer

model-up:
	$(COMPOSE) --profile model up -d --wait ollama

model-pull: model-up
	$(COMPOSE) --profile model exec ollama ollama pull qwen3:4b-instruct-2507-q4_K_M

phase5-real-gate: model-up
	$(UV) run incidentgraph-phase5-gate

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
	npm --prefix frontend test

api:
	$(UV) run incidentgraph-api

worker:
	$(UV) run incidentgraph-worker

frontend:
	npm --prefix frontend run dev

test-frontend:
	npm --prefix frontend test
	npm --prefix frontend run build

test-e2e:
	npm --prefix frontend run test:e2e

coverage:
	$(UV) run pytest -m "not integration" --cov --cov-report=term-missing

test-integration:
	RUN_INTEGRATION=1 $(UV) run pytest -m "integration and not lab_integration and not graph_integration" -v

test-phase6-integration:
	RUN_INTEGRATION=1 $(UV) run pytest tests/integration/test_durable_queue.py -v
	RUN_INVESTIGATOR_INTEGRATION=1 $(UV) run pytest tests/integration/test_phase5_investigator.py -k "postgres_checkpointer or review_interrupt or queue_lease or budgeted_follow_up" -v

test-lab-integration:
	RUN_LAB_INTEGRATION=1 $(UV) run pytest -m lab_integration -v

test-graph-integration:
	RUN_GRAPH_INTEGRATION=1 $(UV) run pytest -m graph_integration -v

test-retrieval-integration:
	RUN_RETRIEVAL_INTEGRATION=1 $(UV) run pytest -m retrieval_integration -v

test-investigator-integration:
	RUN_INVESTIGATOR_INTEGRATION=1 $(UV) run pytest -m investigator_integration -v

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run mypy
	npm --prefix frontend run build
