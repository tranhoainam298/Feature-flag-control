# S01: Database — SQLAlchemy Models & Alembic Migration 18 Bảng

## Ngày hoàn thành
2026-09-16

## Implemented
- **Toàn bộ 18 SQLAlchemy 2.0 Models (`backend/app/models/`)**:
  - `Organization`: Quản lý tổ chức (`slug` UNIQUE, UUID PK).
  - `User`: Người dùng hệ thống (`email` UNIQUE, `password_hash`, `is_active`).
  - `Membership`: Quan hệ user-organization với `member_role` enum (`OWNER`, `ADMIN`, `DEVELOPER`, `VIEWER`), ràng buộc `UNIQUE(user_id, organization_id)`.
  - `Project`: Dự án trực thuộc organization (`default_stale_days=30`, `UNIQUE(organization_id, slug)`).
  - `Environment`: Môi trường triển khai (`ruleset_version` BIGINT default=0 phục vụ ETag/cache, `UNIQUE(project_id, key)`).
  - `ApiKey`: Khóa xác thực SDK (`key_hash` SHA-256, `key_prefix`, `scope`, **tuyệt đối không lưu raw key**, partial index `idx_apikey_hash` lọc `revoked_at IS NULL`).
  - `Flag`: Feature toggle (`key` với CHECK constraint regex `^[a-zA-Z0-9._-]+$`, `type`, `toggle_kind`, `tags`, `archived_at` soft delete, partial index `idx_flag_project_key` lọc `archived_at IS NULL`).
  - `Variation`: Giá trị trả về của flag (`value` JSONB, `UNIQUE(flag_id, key)`).
  - `FlagEnvironmentSetting`: Cấu hình toggle trên từng môi trường (`enabled`, `default_variation_id`, `off_variation_id`, `bucketing_key`, index `idx_fes_env_flag`).
  - `Segment`: Phân khúc người dùng (`conditions` JSONB, GIN index `idx_segment_cond_gin`).
  - `TargetingRule`: Luật nhắm chọn (`priority`, `conditions` JSONB, `distribution` JSONB, index `idx_rule_fes_priority`).
  - `IndividualOverride`: Ghi đè cá nhân cho context_key cụ thể (`UNIQUE(flag_environment_setting_id, context_key)`).
  - `ConfigNamespace`: Không gian cấu hình ứng dụng (`format` JSON/YAML/PROPERTIES, `UNIQUE(environment_id, name)`).
  - `ConfigItem`: Tham số cấu hình nháp (`key` với CHECK constraint regex `^[a-zA-Z0-9._-]+$`, `value_type`, `is_secret`, `json_schema`).
  - `ConfigRelease`: Bản phát hành cấu hình bất biến (`snapshot` JSONB lưu toàn bộ key-value không lưu diff, `UNIQUE(namespace_id, version)`).
  - `AuditLog`: Nhật ký kiểm toán append-only (**không có `deleted_at`** và không expose xóa, `BRIN(created_at)` index và btree `idx_audit_entity`).
  - `ChangeRequest`: Yêu cầu phê duyệt thay đổi (`payload` JSONB, `status` enum, `scheduled_at`, `applied_at`).
  - `EvaluationEvent`: Nhật ký đánh giá flag phân vùng `PARTITION BY RANGE (created_at)` theo ngày và default partition `evaluation_event_default`.

- **Hệ thống Migration Alembic (`backend/alembic/`)**:
  - `alembic.ini` và `alembic/env.py` hỗ trợ async migration qua `asyncpg`.
  - Migration `001_initial_schema.py` tạo đầy đủ 18 bảng, 7 PostgreSQL native enums, 7 indexes bắt buộc, CHECK constraints và hàm `downgrade()` đầy đủ.

## Tests
- **Số test đã viết**: 5 integration tests tại `backend/app/tests/integration/test_models.py` + 4 tests tại `test_health.py` = 9 tests.
  1. `test_full_entity_creation_chain`: Tạo và truy vấn thành công chuỗi quan hệ đầy đủ từ Organization đến ChangeRequest và ConfigRelease.
  2. `test_flag_unique_project_id_key`: Kiểm tra ràng buộc duy nhất `UNIQUE(project_id, key)` kích hoạt `IntegrityError` khi trùng lặp.
  3. `test_project_cascade_delete_flags`: Kiểm tra quan hệ CASCADE khi xóa Project thì Flag bị xóa theo.
  4. `test_jsonb_nested_three_levels`: Kiểm tra lưu trữ và đọc lại chính xác cấu trúc điều kiện lồng 3 tầng `AND`/`OR` trong JSONB.
  5. `test_flag_key_regex_check_constraint`: Kiểm tra CHECK constraint regex `^[a-zA-Z0-9._-]+$` bắt lỗi khi key chứa ký tự không hợp lệ.
- **Kiểm tra Migration Round-trip**:
  - `alembic upgrade head` chạy thành công trên cơ sở dữ liệu trống.
  - `alembic downgrade base` dọn sạch toàn bộ bảng và enums.
  - `alembic upgrade head` tái tạo toàn bộ 18 bảng sạch sẽ không lỗi.
- **Kết quả kiểm thử**: **9 passed in 1.25s (100%)**.
- **Linter & Type Check**: `make lint` đạt **All checks passed!** trên 22 source files.

## Coverage Report
| Module | Coverage |
|--------|----------|
| `app/models/` | 100% |
| `app/core/` | 90% |
| `app/main.py` | 100% |
| **Tổng thể Slice 1** | **~94%** |

## Known Issues
- Không có lỗi tồn đọng ở tầng database.
- Tầng API Auth và CRUD chưa được triển khai (thuộc phạm vi S03/S04).

## Dependencies
- Slice này phụ thuộc: S00 (Bootstrap, Docker Compose).
- Slice phụ thuộc slice này: S03 (Auth), S04 (CRUD Org/Project/Env), và toàn bộ các slice nghiệp vụ tiếp theo.

## Next
- Slice tiếp theo: **S03 — Auth: Đăng ký, đăng nhập, JWT + refresh token**.
