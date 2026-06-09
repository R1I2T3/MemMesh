compose-up:
	docker compose up -d
dev-backend:
	uv run --project backend uvicorn backend.main:app --reload
dev-frontend:
	cd frontend && npm run dev
dev-worker:
	uv run --project backend celery -A backend.tasks.celery_app worker --loglevel=info
test: test-backend test-frontend test-e2e
test-backend:
	uv run --project backend pytest backend/tests/ -v
test-frontend:
	cd frontend && npx vitest run
test-e2e:
	npx playwright test
production-up: compose-up
	cd frontend && npm run build
	uv run --project backend uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
db-migrate:
	cd backend && uv run alembic revision --autogenerate -m "auto"
db-upgrade:
	cd backend && uv run alembic upgrade head
