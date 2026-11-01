.PHONY: up down migrate seed scrape backend test

up:
	docker compose up -d

down:
	docker compose down

migrate:
	cd backend && .venv/bin/alembic upgrade head

backend-setup:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pipeline-setup:
	cd pipeline && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

scrape-dry:
	pipeline/.venv/bin/python -m pipeline.scraper.main scrape --source osm --dry-run

scrape:
	pipeline/.venv/bin/python -m pipeline.scraper.main scrape --source osm

test:
	cd backend && .venv/bin/python -m pytest -q
	pipeline/.venv/bin/python -m pytest pipeline/tests -q

test-db:
	psql -d postgres -c "CREATE ROLE shuvit LOGIN SUPERUSER PASSWORD 'shuvit'" || true
	createdb -O shuvit shuvit || true
	createdb -O shuvit shuvit_test || true

setup: up backend-setup pipeline-setup
	@echo "Waiting for database..."
	@sleep 3
	$(MAKE) migrate
	@echo "Setup complete! Run 'make backend' to start the API server."
