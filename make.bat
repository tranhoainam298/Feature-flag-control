@echo off
set TARGET=%1
if "%TARGET%"=="" set TARGET=up

if "%TARGET%"=="up" (
    docker compose up -d --build
) else if "%TARGET%"=="down" (
    docker compose down
) else if "%TARGET%"=="logs" (
    docker compose logs -f
) else if "%TARGET%"=="migrate" (
    docker compose exec api alembic upgrade head
) else if "%TARGET%"=="seed" (
    docker compose exec api python -m app.seed
) else if "%TARGET%"=="test" (
    docker compose exec -T api pytest
) else if "%TARGET%"=="test-engine" (
    docker compose exec -T api pytest app/engine
) else if "%TARGET%"=="lint" (
    docker compose exec -T api ruff check .
    docker compose exec -T api mypy app
) else if "%TARGET%"=="format" (
    docker compose exec -T api ruff format .
) else if "%TARGET%"=="clean" (
    docker compose down -v
) else (
    echo Unknown target: %TARGET%
    echo Available targets: up, down, logs, migrate, seed, test, test-engine, lint, format, clean
    exit /b 1
)
