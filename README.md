# FlagOps — Feature Flag & Application Configuration Service

FlagOps là nền tảng quản trị Feature Flag và Cấu hình ứng dụng tập trung, tuân thủ chuẩn OpenFeature (CNCF).

## Quick Start

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:3000
```

## Kiến trúc 4 Containers

- **api**: FastAPI (Python 3.12) - Cổng dịch vụ Quản trị (`/api/v1`) và Đánh giá (`/eval/v1`), expose cổng `8000`.
- **web**: React 18 + TypeScript + Vite + Tailwind CSS - Dashboard giao diện quản trị, expose cổng `3000`.
- **postgres**: PostgreSQL 16 Alpine - Cơ sở dữ liệu chính, expose cổng `5432`.
- **redis**: Redis 7 Alpine - Bộ nhớ đệm cache và Pub/Sub invalidation, expose cổng `6379`.

## Lệnh thường dùng

| Lệnh | Chức năng |
|------|-----------|
| `make up` | Khởi động toàn bộ container trong nền |
| `make down` | Dừng các container |
| `make logs` | Theo dõi logs thời gian thực |
| `make test` | Chạy bộ kiểm thử tự động pytest |
| `make lint` | Kiểm tra định dạng và type hints (`ruff` + `mypy`) |
| `make clean` | Dừng và xóa toàn bộ volumes dữ liệu |
