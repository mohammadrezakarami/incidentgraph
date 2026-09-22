UV := UV_PYTHON_INSTALL_DIR='$(CURDIR)/.tools/python' UV_CACHE_DIR='$(CURDIR)/.tools/cache' .tools/uv
COMPOSE := docker compose -f ops/compose.yaml --env-file .env

.PHONY: doctor bootstrap up down migrate smoke test coverage test-integration lint typecheck

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

smoke:
	$(UV) run incidentgraph check-connections

test:
	$(UV) run pytest -m "not integration"

coverage:
	$(UV) run pytest -m "not integration" --cov --cov-report=term-missing

test-integration:
	RUN_INTEGRATION=1 $(UV) run pytest -m integration -v

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run mypy
