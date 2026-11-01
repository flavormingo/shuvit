.PHONY: up down migrate seed scrape backend test

# Start local dev services (PostgreSQL + Redis)
up:
	docker compose up -d

# Stop local dev services
down:
	docker compose down

# Run database migrations
migrate:
	cd backend && .venv/bin/alembic upgrade head

# Install backend dependencies
backend-setup:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# Run backend server
backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Install pipeline dependencies
pipeline-setup:
	cd pipeline && python3 -m venv .venv && .venv/bin/pip install -e .

# Scrape Houston skateparks (dry run)
scrape-dry:
	pipeline/.venv/bin/python -m pipeline.scraper.main scrape --source osm --dry-run

# Scrape Houston skateparks (load into DB)
scrape:
	pipeline/.venv/bin/python -m pipeline.scraper.main scrape --source osm

# Run backend tests
test:
	cd backend && .venv/bin/pytest -v

# Full local setup
setup: up backend-setup pipeline-setup
	@echo "Waiting for database..."
	@sleep 3
	$(MAKE) migrate
	@echo "Setup complete! Run 'make backend' to start the API server."
