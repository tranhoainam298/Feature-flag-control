---
name: flagops-architecture
description: >
  Bản đồ kiến trúc FlagOps, cây thư mục, quy tắc phân tầng, thứ tự slice.
  Nạp skill này ở ĐẦU MỌI phiên làm việc.
---

# Kiến trúc FlagOps

## 1. Tổng quan hệ thống

FlagOps là nền tảng quản trị Feature Flag và Cấu hình ứng dụng, gồm 4 thành phần chính:
- **Core API** (FastAPI) — quản trị + đánh giá
- **Dashboard** (React 18 + TypeScript + Vite)
- **SDK** (Python server-side, JavaScript client-side)
- **Tools** (flag-scanner CLI, load test)

Hạ tầng: PostgreSQL 16, Redis 7, OpenTelemetry.

## 2. Cây thư mục chuẩn

```
flagops/
├── docker-compose.yml
├── docker-compose.dev.yml
├── Makefile
├── README.md
├── AGENTS.md
├── docs/
│   ├── 01-srs.md
│   ├── 02-architecture.md
│   ├── 03-data-model.md
│   ├── 04-api-spec.yaml          # OpenAPI 3.1
│   ├── 05-evaluation-algorithm.md
│   ├── adr/                      # Architecture Decision Records
│   ├── progress/                 # Tiến độ sau mỗi slice
│   └── diagrams/
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── core/                 # config, security, deps, exceptions
│       ├── models/               # SQLAlchemy models
│       ├── schemas/              # Pydantic v2 schemas
│       ├── api/
│       │   ├── admin/            # /api/v1/* — JWT auth
│       │   └── eval/             # /eval/v1/* — API key auth
│       ├── services/             # business logic
│       ├── repositories/         # data access layer
│       ├── engine/               # ★ EVALUATION ENGINE — PURE, KHÔNG I/O
│       │   ├── evaluator.py
│       │   ├── matcher.py
│       │   ├── bucketing.py
│       │   └── operators.py
│       ├── realtime/             # SSE hub
│       └── jobs/                 # APScheduler
├── frontend/
│   ├── package.json
│   └── src/
│       ├── pages/
│       ├── features/             # flags/, config/, segments/, audit/
│       ├── components/
│       └── lib/
├── sdk/
│   ├── python/
│   │   └── flagops/
│   └── javascript/
│       └── src/
├── demo-app/
├── tools/
│   └── flag-scanner/
├── load-tests/
│   └── k6/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

## 3. Quy tắc phụ thuộc một chiều (TUYỆT ĐỐI)

```
api (routers) → services → repositories → models
                    ↑
              engine (thuần)
```

### Quy tắc bắt buộc:
- **api** chỉ gọi **services**, KHÔNG gọi trực tiếp repositories hoặc models
- **services** gọi **repositories** để truy cập dữ liệu
- **repositories** tương tác trực tiếp với **models** (SQLAlchemy)
- **engine** KHÔNG ĐƯỢC import bất cứ thứ gì ở tầng trên (api, services, repositories)
- **engine** KHÔNG ĐƯỢC import sqlalchemy, redis, httpx, fastapi, datetime.now, random, os.environ

### Ví dụ ĐÚNG:
```python
# backend/app/services/evaluation_service.py
from app.repositories.flag_repository import FlagRepository
from app.engine.evaluator import evaluate

class EvaluationService:
    def __init__(self, flag_repo: FlagRepository):
        self.flag_repo = flag_repo

    async def evaluate_flag(self, flag_key: str, context: dict) -> EvaluationResult:
        ruleset = await self.flag_repo.get_ruleset(env_id)  # I/O ở service
        return evaluate(ruleset, context)                    # engine thuần
```

### Ví dụ SAI:
```python
# ❌ Engine import tầng trên
# backend/app/engine/evaluator.py
from app.repositories.flag_repository import FlagRepository  # CẤM!
from sqlalchemy import select                                  # CẤM!
```

## 4. Tách hai đường đọc/ghi

| Đường | Base path | Auth | Lưu lượng | Rate limit |
|-------|-----------|------|-----------|------------|
| Quản trị (Admin) | `/api/v1/*` | JWT Bearer | Thấp | Thoáng |
| Đánh giá (Eval) | `/eval/v1/*` | `X-FlagOps-Key` header | Cực cao | Chặt |

**Router admin và router eval PHẢI ở thư mục riêng biệt**: `api/admin/` và `api/eval/`.

## 5. Thứ tự 23 slice (KHÔNG phá slice trước)

Thực hiện ĐÚNG thứ tự. Slice sau KHÔNG được phá chức năng slice trước.

| # | Slice | Sprint | Ưu tiên |
|---|-------|--------|---------|
| S01 | Docker Compose + CI khung | 0 | MUST |
| S02 | Migration Alembic toàn bộ bảng | 1 | MUST |
| S03 | Auth: đăng ký, đăng nhập, JWT + refresh | 1 | MUST |
| S04 | CRUD organization / project / environment | 1 | MUST |
| S05 | RBAC: decorator kiểm quyền theo vai trò | 1 | MUST |
| S06 | API key: sinh, hash, xác thực, thu hồi | 1 | MUST |
| S07 | Middleware audit log | 1 | MUST |
| S08 | CRUD flag + variations | 2 | MUST |
| S09 | flag_environment_setting: bật/tắt theo env | 2 | MUST |
| S10 | Engine v1: boolean, enabled/disabled, default | 2 | MUST |
| S11 | API evaluate + cache Redis + Pub/Sub invalidation | 2 | MUST |
| S12 | CRUD segment + bộ toán tử đầy đủ | 3 | MUST |
| S13 | Targeting rule + priority + individual override | 3 | MUST |
| S14 | Bucketing MurmurHash3 + percentage rollout | 3 | MUST |
| S15 | API simulate — mô phỏng đánh giá | 3 | MUST |
| S16 | CRUD namespace + config item (nháp) | 4 | MUST |
| S17 | Publish / release / diff / rollback | 4 | MUST |
| S18 | Mã hóa secret (AES-256-GCM) + JSON Schema validate | 4 | MUST |
| S19 | GET /eval/v1/ruleset + ETag/304 + SSE hub | 5 | MUST |
| S20 | SDK Python: in-process, polling, SSE, fail-safe | 5 | MUST |
| S21 | OpenFeature Provider | 5 | MUST |
| S22 | Change Request + scheduled change | 6 | SHOULD |
| S23 | Flag lifecycle + debt score + flag-scanner CLI | 6 | SHOULD |

## 6. Quy tắc "không phá slice trước"

- Mỗi slice khi hoàn thành phải CÒN hoạt động sau khi các slice tiếp theo được thêm vào
- KHÔNG refactor phá migration đã commit
- KHÔNG đổi chữ ký API đã có client gọi mà không tạo version mới
- Test của slice trước phải VẪN XANH sau slice sau

## 7. Checklist tự kiểm tra

- [ ] Mọi file mới nằm đúng thư mục trong cây thư mục chuẩn
- [ ] Không có import ngược chiều (engine → services, repositories → api)
- [ ] Router admin ở `api/admin/`, router eval ở `api/eval/`
- [ ] Engine không import bất kỳ thư viện I/O nào
- [ ] Slice hiện tại không phá test của slice trước
- [ ] Đã đọc kế hoạch Phần E (kiến trúc) trước khi thêm module mới
