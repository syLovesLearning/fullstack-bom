.PHONY: dev prod test

dev:
	@echo "Starting backend (ENV=dev, port 8001) + frontend (port 5175)..."
	@trap 'kill 0' EXIT; \
	(cd backend && ENV=dev .venv/bin/uvicorn src.main:app --reload --port 8001) & \
	(cd frontend && npm run dev) & \
	wait

prod:
	@echo "Starting backend (ENV=prod, port 8001) + frontend (port 5175)..."
	@trap 'kill 0' EXIT; \
	(cd backend && ENV=prod .venv/bin/uvicorn src.main:app --port 8001) & \
	(cd frontend && npm run dev) & \
	wait

test:
	cd backend && .venv/bin/pytest -q
