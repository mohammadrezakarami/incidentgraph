UV := UV_PYTHON_INSTALL_DIR='$(CURDIR)/.tools/python' UV_CACHE_DIR='$(CURDIR)/.tools/cache' .tools/uv
COMPOSE_PROJECT ?= incidentgraph
ENV_FILE ?= .env
RESOURCE_PROFILE ?= standard
SCENARIO ?= healthy
BACKUP ?= backups/incidentgraph-app.dump
COMPOSE_FILES := -f ops/compose.yaml
ifeq ($(RESOURCE_PROFILE),low)
COMPOSE_FILES += -f ops/compose.low-resource.yaml
endif
COMPOSE := docker compose -p $(COMPOSE_PROJECT) $(COMPOSE_FILES) --env-file $(ENV_FILE)
RELEASE_COMPOSE := docker compose -p $(COMPOSE_PROJECT) -f ops/compose.yaml -f ops/compose.release.yaml $(if $(filter low,$(RESOURCE_PROFILE)),-f ops/compose.low-resource.yaml) --env-file $(ENV_FILE)

.PHONY: doctor bootstrap configure up down reset migrate retention-status seed ingest verify-ingestion benchmark-embeddings retrieve evaluate-retrieval-dev evaluate-dev verify-retrieval build-incident-eval verify-incident-eval investigator-status setup-checkpointer model-up model-pull phase5-real-gate verify-phase9-freeze verify-phase9-v2-freeze verify-phase9-v3-freeze verify-phase9-v4-freeze evaluate-test evaluate-phase9-v2 evaluate-phase9-v3 evaluate-phase9-v4 report smoke lab-up lab-migrate lab-ready scenario capture capture-suite verify-captures api worker frontend demo portfolio-screenshots portfolio-verify test test-offline test-frontend test-e2e coverage coverage-all test-integration test-phase6-integration test-lab-integration test-graph-integration test-retrieval-integration test-investigator-integration lint format-check typecheck release-verify release-build release-up release-down backup-app restore-app

doctor:
	$(UV) run incidentgraph doctor

bootstrap:
	./bootstrap.sh

configure:
	.venv/bin/python scripts/create_local_env.py

up:
	$(COMPOSE) up -d --wait app-db lab-db neo4j

down:
	$(COMPOSE) down

reset:
	@echo "This removes only these Docker volumes: $(COMPOSE_PROJECT)_app-db-data $(COMPOSE_PROJECT)_lab-db-data $(COMPOSE_PROJECT)_neo4j-data $(COMPOSE_PROJECT)_neo4j-logs $(COMPOSE_PROJECT)_prometheus-data $(COMPOSE_PROJECT)_ollama-data"
	@test "$(CONFIRM)" = "DELETE_INCIDENTGRAPH_VOLUMES" || (echo "Re-run with CONFIRM=DELETE_INCIDENTGRAPH_VOLUMES"; exit 2)
	$(COMPOSE) down
	docker volume rm $(COMPOSE_PROJECT)_app-db-data $(COMPOSE_PROJECT)_lab-db-data $(COMPOSE_PROJECT)_neo4j-data $(COMPOSE_PROJECT)_neo4j-logs $(COMPOSE_PROJECT)_prometheus-data $(COMPOSE_PROJECT)_ollama-data

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

evaluate-dev: evaluate-retrieval-dev

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

verify-phase9-freeze:
	$(UV) run incidentgraph-phase9-eval verify-freeze

verify-phase9-v2-freeze:
	$(UV) run python -m incidentgraph.phase9_v2_evaluation verify-freeze

verify-phase9-v3-freeze:
	$(UV) run python -m incidentgraph.phase9_v3_evaluation verify-freeze

verify-phase9-v4-freeze:
	$(UV) run python -m incidentgraph.phase9_v4_runner verify-freeze

evaluate-test:
	$(UV) run python -m incidentgraph.phase9_v4_runner verify-freeze
	$(UV) run python -m incidentgraph.release verify-evaluation

evaluate-phase9-v2:
	@echo "Phase 9 v2 is a retained historical regression result; new runs are not authorized."
	@exit 2

evaluate-phase9-v3:
	@echo "Phase 9 v3 is a retained historical evaluation result; new runs are not authorized."
	@exit 2

evaluate-phase9-v4:
	@echo "A new stochastic run requires a separately frozen dataset; see notebooks/phase9_evaluation.ipynb."
	@exit 2

report:
	$(UV) run python -m incidentgraph.release report

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

capture: scenario

capture-suite:
	$(UV) run incidentgraph-lab capture-suite

verify-captures:
	$(UV) run incidentgraph-lab verify-captures

api:
	$(UV) run incidentgraph-api

worker:
	$(UV) run incidentgraph-worker

frontend:
	npm --prefix frontend run dev

demo: up migrate
	npm --prefix frontend run test:e2e

portfolio-screenshots:
	$(COMPOSE) up -d --wait app-db
	$(UV) run incidentgraph migrate
	mkdir -p artifacts/portfolio
	INCIDENTGRAPH_PORTFOLIO_OUTPUT="$(CURDIR)/artifacts/portfolio" npm --prefix frontend run test:e2e

portfolio-verify:
	$(UV) run pytest tests/unit/test_portfolio.py -q

test:
	$(UV) run pytest -m "not integration"
	npm --prefix frontend test

test-offline:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m pytest -m "not integration"
	npm --prefix frontend test
	npm --prefix frontend run build

test-frontend:
	npm --prefix frontend test
	npm --prefix frontend run build

test-e2e:
	npm --prefix frontend run test:e2e

coverage:
	$(UV) run pytest -m "not integration" \
		--cov=incidentgraph.models --cov=incidentgraph.auth \
		--cov=incidentgraph.api_support --cov=incidentgraph.investigation_tools \
		--cov=incidentgraph.investigator --cov=incidentgraph.retrieval \
		--cov=incidentgraph.phase9_repair --cov=incidentgraph.phase9_v4_evaluation \
		--cov-branch --cov-report=term-missing

coverage-all:
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

format-check:
	$(UV) run ruff format --check src/incidentgraph/config.py src/incidentgraph/release.py src/incidentgraph/worker.py scripts/create_local_env.py tests/unit/test_config.py tests/unit/test_create_local_env.py tests/unit/test_release.py

typecheck:
	$(UV) run mypy
	npm --prefix frontend run build

release-verify:
	$(UV) run python -m incidentgraph.release verify
	$(RELEASE_COMPOSE) config --quiet

release-build:
	docker build --tag incidentgraph-core:0.1.0 .

release-up: up migrate
	$(RELEASE_COMPOSE) up -d --wait api

release-down:
	$(RELEASE_COMPOSE) down

backup-app:
	$(UV) run python -m incidentgraph.release backup-app --project-name "$(COMPOSE_PROJECT)" --output "$(BACKUP)"

restore-app:
	$(UV) run python -m incidentgraph.release restore-app --project-name "$(COMPOSE_PROJECT)" --input "$(BACKUP)" --confirm "$(CONFIRM)"
