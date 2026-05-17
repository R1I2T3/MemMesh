.PHONY: stack-up stack-down test-unit test-e2e format lint

PID_DIR := .pids

stack-up: | $(PID_DIR)
	docker compose up -d
	@echo "Starting uvicorn on port 7777..."
	uv run uvicorn agentos:app --port 7777 --reload & echo $$! > $(PID_DIR)/uvicorn.pid
	@echo "Starting Next.js dev server..."
	(cd frontend && npm run dev) & echo $$! > $(PID_DIR)/next.pid
	@echo "Stack is up. PIDs tracked in $(PID_DIR)/"

stack-down:
	docker compose down
	@if [ -f $(PID_DIR)/uvicorn.pid ]; then \
		kill $$(cat $(PID_DIR)/uvicorn.pid) 2>/dev/null || true; \
		rm -f $(PID_DIR)/uvicorn.pid; \
	fi
	@if [ -f $(PID_DIR)/next.pid ]; then \
		kill $$(cat $(PID_DIR)/next.pid) 2>/dev/null || true; \
		rm -f $(PID_DIR)/next.pid; \
	fi
	@echo "Stack is down."

$(PID_DIR):
	mkdir -p $(PID_DIR)

test-unit:
	uv run pytest tests/unit -v

test-e2e:
	uv run pytest tests/e2e -m e2e -v

test-all: test-unit test-e2e
