.PHONY: stack-up stack-down test-unit test-e2e format lint

stack-up:
	docker compose up -d
	uv run uvicorn agentos:app --port 7777 --reload &
	cd frontend && npm run dev &

stack-down:
	docker compose down
	pkill -f uvicorn || true
	pkill -f "next dev" || true

test-unit:
	uv run pytest tests/unit -v

test-e2e:
	uv run pytest tests/e2e -m e2e -v

test-all: test-unit test-e2e
