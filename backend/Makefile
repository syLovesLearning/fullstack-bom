.PHONY: dev migrate verify test

dev:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	psql "$${PG_DSN:-postgresql://shenyang@localhost:5432/rag_db}" -f scripts/init_db.sql

verify:
	python3 -m compileall -q src tests

test:
	pytest -q
