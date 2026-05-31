VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
UVICORN := $(VENV)/bin/uvicorn

.PHONY: check-deps install setup migrate seed-admin run run-bg stop test lint format clean reset-db

check-deps:
	@echo "Checking prerequisites..."
	@python3 --version | grep -q "3.1[1-9]\\|3.[2-9][0-9]" || (echo "ERROR: Python 3.11+ required" && exit 1)
	@which pip3 > /dev/null || (echo "ERROR: pip3 not found" && exit 1)
	@echo "All prerequisites met."

install: check-deps
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ".env created from .env.example — edit it with your settings."; \
	else \
		echo ".env already exists, skipping."; \
	fi

migrate:
	@mkdir -p data
	$(PYTHON) -c "from db.sqlite import run_migrations; run_migrations()"
	@echo "Migrations applied."

seed-admin:
	$(PYTHON) -c "from db.sqlite import seed_admin; seed_admin()"
	@echo "Superadmin seeded."

run:
	$(UVICORN) main:app --host $${API_HOST:-127.0.0.1} --port $${API_PORT:-8000} --reload

run-bg:
	$(UVICORN) main:app --host $${API_HOST:-127.0.0.1} --port $${API_PORT:-8000} &
	@echo $$! > .pid
	@echo "Server started (PID: $$(cat .pid))"

stop:
	@if [ -f .pid ]; then \
		kill $$(cat .pid) 2>/dev/null || true; \
		rm .pid; \
		echo "Server stopped."; \
	else \
		echo "No .pid file found."; \
	fi

test:
	$(PYTEST) tests/ -v

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/black --check .

format:
	$(VENV)/bin/black .
	$(VENV)/bin/isort .

clean:
	rm -rf $(VENV) data __pycache__ .pid .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

reset-db:
	rm -f data/db.sqlite3
	$(MAKE) migrate
	$(MAKE) seed-admin
