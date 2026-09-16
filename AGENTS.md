# FlagOps — Agent Guide

**FlagOps** là nền tảng quản trị Feature Flag và Cấu hình ứng dụng.
Hệ thống cho phép bật/tắt tính năng tại runtime, rollout dần theo phần trăm,
quản lý cấu hình tập trung có version và rollback, theo dõi vòng đời flag.
Stack: Python 3.12 + FastAPI + SQLAlchemy 2.x + Alembic + Pydantic v2 + PostgreSQL + Redis.
Tuân thủ chuẩn OpenFeature (CNCF).

---

## Lệnh thường dùng

| Lệnh | Chức năng |
|-------|-----------|
| `make up` | `docker compose up -d --build` |
| `make migrate` | `alembic upgrade head` |
| `make seed` | Nạp dữ liệu mẫu |
| `make test` | `pytest` toàn bộ, fail-under=75% |
| `make test-engine` | Chỉ test engine, fail-under=95% |
| `make lint` | `ruff check` + `mypy` + `eslint` |

---

## Skills — Nạp đúng skill trước khi làm việc

| # | Skill | Nạp khi nào |
|---|-------|-------------|
| 1 | `flagops-architecture` | **Đầu MỌI phiên làm việc** — cây thư mục, phân tầng, thứ tự slice |
| 2 | `python-fastapi-backend` | Làm bất kỳ endpoint, service, hoặc repository nào |
| 3 | `postgres-alembic-migrations` | Thêm/sửa bảng, tạo migration |
| 4 | `evaluation-engine-purity` | Động vào bất kỳ file nào trong `backend/app/engine/` |
| 5 | `python-testing-pytest` | Viết bất kỳ test nào |
| 6 | `api-contract-rest` | Tạo hoặc sửa endpoint |
| 7 | `security-hardening` | Làm auth, API key, config secret, review bảo mật |
| 8 | `frontend-react-dashboard` | Làm bất kỳ màn hình frontend nào |
| 9 | `python-sdk-design` | Làm `sdk/python/` |
| 10 | `docs-adr-progress` | Kết thúc một slice, viết ADR |

---

## Skill bên ngoài (vendor từ GitHub)

| Tên skill | Dùng khi nào | Đường dẫn full skill |
|-----------|--------------|----------------------|
| `ponytail` | MỌI lúc viết code Python mới (tối giản, chống over-engineering) | `.claude/skills/ponytail/SKILL.md` |
| `taste-skill` | CHỈ khi làm UI dashboard (slice 16, 17) — thẩm mỹ anti-slop | `.claude/skills/taste-skill/SKILL.md` |
| `web-design-guidelines` | Khi thiết kế, review giao diện web và trải nghiệm UI/UX | `.claude/skills/web-design-guidelines/SKILL.md` |
| `writing-guidelines` | Khi viết tài liệu, microcopy, thông báo lỗi, API docstring | `.claude/skills/writing-guidelines/SKILL.md` |
| `tdd` | CHỈ khi viết engine/logic thuần trước khi code (Red-Green-Refactor) | `.claude/skills/tdd/SKILL.md` |
| `systematic-debugging` | Khi gặp bug khó, test fail, hoặc hành vi không xác định | `.claude/skills/systematic-debugging/SKILL.md` |
| `verification-before-completion` | CUỐI MỌI slice, trước khi báo cáo xong | `.claude/skills/verification-before-completion/SKILL.md` |

---

## Quy tắc bất di bất dịch

1. **Evaluation engine phải pure, không I/O** — `evaluate(ruleset, context) → result`. Không query DB, không gọi mạng, không đọc đồng hồ hệ thống trong engine.
2. **Không đặt business logic ở frontend** — evaluate, diff, debt score, bucketing đều phải gọi API backend.
3. **Không copy code từ Flagsmith/Unleash/GO Feature Flag** — chỉ học thiết kế, tự viết implementation. Ghi nguồn tham chiếu trong ADR.
4. **MUST xong hết mới làm SHOULD** — không nhảy sang tính năng SHOULD khi còn MUST chưa hoàn thành.
5. **Không phá slice trước** — test của slice trước phải vẫn xanh sau khi thêm slice mới.
6. **Phụ thuộc một chiều**: `api → services → repositories → models`. Engine không import tầng trên.
7. **Không sửa migration đã commit** — tạo migration mới.
8. **SDK không ném exception** — luôn trả default value, mất kết nối dùng cache cuối cùng.
9. **Org A truy cập org B → 404** (không 403) — tránh lộ sự tồn tại resource.
10. **Mọi commit theo Conventional Commits** — `feat(scope):`, `fix(scope):`, `test(scope):`.

---

## Thứ tự 23 slice

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
