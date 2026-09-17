.PHONY: up down logs migrate seed test test-engine lint format clean

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api alembic upgrade head
	docker compose exec api python -m app.seed

test:
	docker compose exec -T api pytest

test-engine:
	docker compose exec -T api pytest app/tests/unit/engine --cov=app/engine --cov-fail-under=95

lint:
	docker compose exec -T api ruff check .
	docker compose exec -T api mypy app

format:
	docker compose exec -T api ruff format .

clean:
	docker compose down -v
