# Arxiu de notes — top-level orchestration
# Use: make help

SHELL := /bin/bash
COMPOSE_DEV := docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml --env-file .env
COMPOSE_TEST := docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.test.yml --env-file .env
COMPOSE_PROD := docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml --env-file .env.production

.DEFAULT_GOAL := help

.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# --- Setup -------------------------------------------------------------------

.PHONY: bootstrap
bootstrap:  ## First-time local setup: copy .env, install deps, build images
	@if [ ! -f .env ]; then cp .env.example .env && echo "✓ .env created — edit secrets before running"; fi
	@$(MAKE) jwt-keys
	@$(MAKE) build

.PHONY: jwt-keys
jwt-keys:  ## Generate RSA keypair for JWT signing (writes to ./secrets/)
	@mkdir -p secrets
	@if [ ! -f secrets/jwt_private.pem ]; then \
		openssl genpkey -algorithm RSA -out secrets/jwt_private.pem -pkeyopt rsa_keygen_bits:2048 && \
		openssl rsa -pubout -in secrets/jwt_private.pem -out secrets/jwt_public.pem && \
		chmod 600 secrets/jwt_private.pem && \
		echo "✓ JWT keypair generated in ./secrets/"; \
	else echo "✓ JWT keypair already exists"; fi

# --- Dev ---------------------------------------------------------------------

.PHONY: dev
dev:  ## Start the dev stack (mysql + redis + backend hot-reload + frontend HMR)
	$(COMPOSE_DEV) up --build

.PHONY: dev-detached
dev-detached:  ## Start the dev stack in background
	$(COMPOSE_DEV) up -d --build

.PHONY: down
down:  ## Stop and remove dev containers
	$(COMPOSE_DEV) down

.PHONY: logs
logs:  ## Tail dev stack logs
	$(COMPOSE_DEV) logs -f --tail=100

.PHONY: ps
ps:  ## List running services
	$(COMPOSE_DEV) ps

.PHONY: build
build:  ## Build all docker images
	$(COMPOSE_DEV) build

# --- Backend -----------------------------------------------------------------

.PHONY: backend-shell
backend-shell:  ## Open shell in running backend container
	$(COMPOSE_DEV) exec backend bash

.PHONY: migrate
migrate:  ## Apply database migrations
	$(COMPOSE_DEV) exec backend alembic upgrade head

.PHONY: migration
migration:  ## Generate a new alembic migration. Usage: make migration m="add users table"
	$(COMPOSE_DEV) exec backend alembic revision --autogenerate -m "$(m)"

.PHONY: seed
seed:  ## Populate database with realistic seed data
	$(COMPOSE_DEV) exec backend python -m app.scripts.seed

.PHONY: seed-e2e
seed-e2e:  ## Populate database with deterministic e2e dataset
	$(COMPOSE_DEV) exec backend python -m app.scripts.seed_e2e

# --- Frontend ----------------------------------------------------------------

.PHONY: frontend-shell
frontend-shell:  ## Open shell in running frontend container
	$(COMPOSE_DEV) exec frontend sh

.PHONY: gen-api-types
gen-api-types:  ## Regenerate TypeScript API client from backend OpenAPI spec
	$(COMPOSE_DEV) exec frontend pnpm gen:api

# --- Quality -----------------------------------------------------------------

.PHONY: lint
lint:  ## Lint backend (ruff) and frontend (eslint)
	$(COMPOSE_DEV) exec backend ruff check .
	$(COMPOSE_DEV) exec frontend pnpm lint

.PHONY: format
format:  ## Auto-format backend (ruff) and frontend (prettier)
	$(COMPOSE_DEV) exec backend ruff format .
	$(COMPOSE_DEV) exec frontend pnpm format

.PHONY: typecheck
typecheck:  ## Type-check backend (mypy) and frontend (tsc)
	$(COMPOSE_DEV) exec backend mypy app
	$(COMPOSE_DEV) exec frontend pnpm typecheck

.PHONY: test
test:  ## Run backend (pytest) and frontend (vitest) tests
	$(COMPOSE_DEV) exec backend pytest
	$(COMPOSE_DEV) exec frontend pnpm test

.PHONY: test-backend
test-backend:  ## Run backend tests with coverage
	$(COMPOSE_DEV) exec backend pytest --cov=app --cov-report=term-missing

.PHONY: test-frontend
test-frontend:  ## Run frontend tests with coverage
	$(COMPOSE_DEV) exec frontend pnpm test:cov

.PHONY: e2e
e2e:  ## Run Playwright end-to-end tests against the dev stack
	$(COMPOSE_DEV) exec frontend pnpm e2e

# --- Production --------------------------------------------------------------

.PHONY: prod-build
prod-build:  ## Build production images
	$(COMPOSE_PROD) build

.PHONY: prod-up
prod-up:  ## Start production stack (requires .env.production)
	$(COMPOSE_PROD) up -d

.PHONY: prod-down
prod-down:  ## Stop production stack
	$(COMPOSE_PROD) down

.PHONY: smoke
smoke:  ## Curl-based smoke test against a running stack (BASE_URL=...)
	@bash scripts/smoke.sh

.PHONY: backup
backup:  ## Run a one-off MySQL backup (writes to ./backups/)
	@mkdir -p backups
	$(COMPOSE_DEV) exec -T mysql mysqldump -u root -p$$MYSQL_ROOT_PASSWORD --single-transaction --routines arxiu | gzip > backups/arxiu-$$(date +%Y%m%d-%H%M%S).sql.gz
	@echo "✓ Backup written to ./backups/"

# --- Cleanup -----------------------------------------------------------------

.PHONY: clean
clean:  ## Remove generated artifacts (keeps containers + volumes)
	rm -rf apps/frontend/dist apps/frontend/.vite apps/frontend/coverage \
	       apps/backend/htmlcov apps/backend/.pytest_cache apps/backend/.ruff_cache apps/backend/.mypy_cache \
	       playwright-report test-results

.PHONY: nuke
nuke:  ## STOP and DELETE all containers + volumes (data loss). Confirm with CONFIRM=yes
	@if [ "$(CONFIRM)" != "yes" ]; then echo "Refusing — pass CONFIRM=yes to actually nuke"; exit 1; fi
	$(COMPOSE_DEV) down -v --remove-orphans
