# Makefile (project root) — orchestrates backend + frontend

.PHONY: install setup run test test-e2e clean

install:
	$(MAKE) -C backend install
	cd frontend && npm install

setup:
	$(MAKE) -C backend setup
	$(MAKE) -C backend migrate
	$(MAKE) -C backend seed-admin

run:
	@echo "Starting backend on :8081 and frontend on :5173..."
	@$(MAKE) -C backend run-bg
	@cd frontend && npm run dev

test:
	$(MAKE) -C backend test

test-api:
	$(MAKE) -C backend test

test-e2e:
	cd frontend && npx playwright test

clean:
	$(MAKE) -C backend clean
	cd frontend && rm -rf node_modules .svelte-kit
