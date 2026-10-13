# The project virtualenv is ./venv (uv manages it).
export UV_PROJECT_ENVIRONMENT := venv

.PHONY: install dev db-up db-down migrate test lint fmt smoke

install:          ## install all dependencies into ./venv
	uv sync

dev:              ## run the API locally with reload (uses .env)
	uv run uvicorn --factory app.main:create_app --reload --port 8000

db-up:            ## start local Postgres 18
	docker compose up -d db

db-down:
	docker compose down

migrate:          ## apply sql/ to DATABASE_URL
	uv run python -m app.db.migrator

test:             ## run the test suite (needs Docker for Postgres)
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

smoke:            ## end-to-end checks against BASE_URL (default: local)
	./scripts/smoke_test.sh
