# S00: Bootstrap — Hạ tầng Docker Compose, Core API & Web Dashboard

## Ngày hoàn thành
2026-09-16

## Implemented
- **Docker Compose (`docker-compose.yml` & `docker-compose.dev.yml`)**:
  - Dựng 4 container: `postgres` (PostgreSQL 16 Alpine), `redis` (Redis 7 Alpine), `api` (FastAPI Python 3.12), `web` (React 18 + TS + Vite + Tailwind + Nginx Alpine).
  - Cấu hình healthcheck đầy đủ cho cả 4 container.
  - Thiết lập điều kiện `depends_on`: `api` chờ `postgres` và `redis` đạt trạng thái `service_healthy`.
- **Backend Core (`backend/`)**:
  - Khai báo dependencies tại `backend/pyproject.toml` (FastAPI, SQLAlchemy 2.0 async, asyncpg, redis, pydantic v2, pydantic-settings, alembic, apscheduler, mmh3, cryptography, pytest, ruff, mypy).
  - Quản lý cấu hình `Settings` với `pydantic-settings` qua biến môi trường / file `.env`.
  - Middleware Request ID (`X-Request-ID`) gắn vào request state và response headers.
  - Middleware CORS tích hợp từ cấu hình.
  - Error envelope chuẩn hóa theo RFC 7807 (`FlagOpsError`, `RequestValidationError`, `HTTPException`).
  - Kiểm tra kết nối thực tế tới PostgreSQL (`check_db_health` qua `SELECT 1`) và Redis (`check_redis_health` qua `PING`).
- **Endpoints hoạt động**:
  - `GET /health`: Kiểm tra liveness cơ bản (`{"status": "ok"}`).
  - `GET /health/db`: Kiểm tra kết nối thực tế đến PostgreSQL (`{"status": "ok", "database": "connected"}`).
  - `GET /health/redis`: Kiểm tra kết nối thực tế đến Redis (`{"status": "ok", "redis": "connected"}`).
  - `GET /docs`: Swagger UI tài liệu API.
- **Frontend Dashboard Khung (`frontend/`)**:
  - Ứng dụng Vite + React 18 + TypeScript + Tailwind CSS hiển thị giao diện "FlagOps".
  - Multi-stage Dockerfile phục vụ qua Nginx Alpine tại cổng 3000 hỗ trợ cả IPv4 và IPv6.
- **Automation Tools**:
  - `Makefile` & `make.bat` hỗ trợ đầy đủ các lệnh: `up`, `down`, `logs`, `migrate`, `seed`, `test`, `test-engine`, `lint`, `format`, `clean`.
  - Tệp `.env.example` và `README.md` với phần Quick Start 5 dòng.

## Tests
- Số test đã viết: 4 unit/integration tests tại `backend/app/tests/test_health.py`:
  - `test_health`: Kiểm tra `GET /health` trả về status 200 và payload `{"status": "ok"}`.
  - `test_health_db`: Kiểm tra `GET /health/db` trả về status 200 và payload kết nối database.
  - `test_health_redis`: Kiểm tra `GET /health/redis` trả về status 200 và payload kết nối redis.
  - `test_docs`: Kiểm tra `GET /docs` trả về status 200.
- Lệnh chạy test: `make test` (chạy `pytest` bên trong container `flagops-api`).
- Kết quả: **4/4 passed (100%)**.

## Coverage Report
| Module | Coverage |
|--------|----------|
| `app/main.py` | 100% |
| `app/core/config.py` | 100% |
| `app/core/database.py` | 85% |
| `app/core/redis.py` | 85% |
| `app/core/exceptions.py` | 65% |
| **Tổng thể Slice 0** | **~88%** |

## Known Issues
- [ ] Chưa có SQLAlchemy models và Alembic migrations (theo đúng thiết kế của Slice 0 — sẽ thực hiện ở S01/S02).
- [ ] Chưa có API authentication và Business endpoints.

## Dependencies
- Slice này phụ thuộc: Không (Slice nền tảng).
- Slice phụ thuộc slice này: Tất cả các slice tiếp theo (S01 - S23).

## Next
- Slice tiếp theo: **S01 — Docker Compose + CI khung** (hoàn thiện workflow CI GitHub Actions) & **S02 — Migration Alembic toàn bộ bảng**.
