# S04: Flag Management — Flag, Variation & FlagEnvironmentSetting CRUD

## Ngày hoàn thành
2026-09-16

## Implemented
- **Mô hình dữ liệu & Quan hệ (`backend/app/models/flag.py`)**:
  - `Flag`: Quản lý feature toggle với CHECK constraint regex `key ~ '^[a-zA-Z0-9._-]+$'`, quan hệ `variations` một chiều hỗ trợ eager load `selectinload` chống N+1 query.
  - `Variation`: Giá trị trả về của flag (`value` kiểu JSONB).
  - `FlagEnvironmentSetting`: Cấu hình bật/tắt trên từng môi trường (`enabled`, `default_variation_id`, `off_variation_id`, `bucketing_key`).
- **Quy tắc nghiệp vụ Flag (`backend/app/services/flag.py`)**:
  - **Bất biến Flag Key**: Flag key không thể thay đổi sau khi tạo. Bất kỳ request `PATCH /api/v1/flags/{flag_id}` nào chứa trường `key` đều bị từ chối với HTTP 400 và code `FLAG_KEY_IMMUTABLE`.
  - **Tự động sinh Variation cho BOOLEAN**: Flag kiểu `BOOLEAN` khi tạo tự động sinh 2 variations: `on=true`, `off=false`.
  - **Ràng buộc Variation cho Flag kiểu khác**: Flag kiểu `STRING`, `NUMBER`, `JSON` bắt buộc phải có ít nhất 2 variations (nếu thiếu trả 422).
  - **Kiểm tra khớp kiểu (Type Safety)**: Giá trị variation phải khớp với `flag.type`, nếu không khớp trả HTTP 422 với code `TYPE_MISMATCH`.
  - **Tự động sinh Flag Environment Setting**: Khi tạo flag mới trong project, hệ thống tự động sinh `FlagEnvironmentSetting` cho MỌI environment của project đó với `enabled=False`, gán `default_variation` và `off_variation`.
  - **Tăng Ruleset Version**: Hàm dùng chung `bump_ruleset_version(db, env_id)` tự động tăng `environment.ruleset_version += 1` trên mỗi thao tác ghi (phục vụ ETag và cache invalidation).
  - **Ghi nhật ký kiểm toán (Audit Logging)**: Mọi thao tác tạo, sửa metadata, lưu trữ, khôi phục, và thay đổi cấu hình toggle đều tự động ghi lại `AuditLog` với chi tiết `before` và `after`.
  - **Cô lập môi trường**: Bật/tắt flag ở môi trường Development hoàn toàn độc lập, không làm ảnh hưởng tới Production.
  - **Bảo mật phân quyền & Multi-tenancy**:
    - User thuộc Org A truy cập flag của Org B nhận về HTTP 404 `FLAG_NOT_FOUND` (không trả 403).
    - Role `VIEWER` chỉ được xem flag và settings, cố tình tạo hoặc sửa đổi sẽ nhận HTTP 403 `FORBIDDEN`.
- **Endpoints RESTful (`backend/app/api/v1/flags.py`)**:
  - `GET /api/v1/projects/{project_id}/flags`: Danh sách flag (hỗ trợ lọc theo `tag`, `type`, `archived`, `search`).
  - `POST /api/v1/projects/{project_id}/flags`: Tạo flag + variations trong 1 transaction duy nhất (status 201).
  - `GET /api/v1/flags/{flag_id}`: Chi tiết flag kèm danh sách variations.
  - `PATCH /api/v1/flags/{flag_id}`: Sửa metadata flag (chặn sửa `key`).
  - `POST /api/v1/flags/{flag_id}/archive`: Đánh dấu `archived_at` (soft delete).
  - `POST /api/v1/flags/{flag_id}/restore`: Khôi phục flag đã archive (`archived_at = None`).
  - `GET /api/v1/flags/{flag_id}/environments/{env_id}`: Lấy cấu hình flag trên một environment cụ thể.
  - `PUT /api/v1/flags/{flag_id}/environments/{env_id}`: Cập nhật cấu hình toggle (bật/tắt, variation mặc định, bucketing key).

## Tests & Definition of Done
- **Bộ kiểm thử tự động tại `backend/app/tests/test_flags.py` (21 test cases)**:
  1. `test_create_flag_boolean_auto_generates_variations`: Tạo flag boolean tự sinh `on=true`, `off=false`.
  2. `test_create_flag_boolean_auto_generates_env_settings`: Tự sinh setting cho mọi env với `enabled=false`.
  3. `test_create_flag_string_missing_variations_422`: Tạo flag string không có variation trả 422.
  4. `test_create_flag_string_single_variation_422`: Tạo flag string chỉ có 1 variation trả 422.
  5. `test_create_flag_string_with_valid_variations`: Tạo flag string với 3 variations thành công.
  6. `test_create_flag_number_with_valid_variations`: Tạo flag number với float/int thành công.
  7. `test_create_flag_json_with_valid_variations`: Tạo flag json với dict thành công.
  8. `test_create_flag_type_mismatch_boolean_422`: Sai kiểu boolean trả 422 `TYPE_MISMATCH`.
  9. `test_create_flag_type_mismatch_string_422`: Sai kiểu string trả 422 `TYPE_MISMATCH`.
  10. `test_create_flag_type_mismatch_number_422`: Sai kiểu number trả 422 `TYPE_MISMATCH`.
  11. `test_create_flag_type_mismatch_json_422`: Sai kiểu json trả 422 `TYPE_MISMATCH`.
  12. `test_create_flag_duplicate_key_conflict_409`: Trùng lặp flag key trong cùng project trả 409 `CONFLICT`.
  13. `test_patch_flag_key_immutable_400`: Cố sửa key trả 400 `FLAG_KEY_IMMUTABLE`.
  14. `test_patch_flag_metadata_success`: Cập nhật name, description, tags thành công.
  15. `test_archive_and_restore_flag`: Lưu trữ flag loại khỏi danh sách active, khôi phục flag trở lại danh sách.
  16. `test_toggle_flag_in_dev_does_not_affect_prod`: Bật toggle ở dev không ảnh hưởng prod.
  17. `test_ruleset_version_increments_on_every_write`: Kiểm tra `ruleset_version` tăng đúng sau mỗi lần ghi.
  18. `test_audit_log_recorded_with_before_and_after`: Kiểm tra audit log lưu đúng dữ liệu trước/sau.
  19. `test_list_flags_filter_by_tag_and_type_and_search`: Lọc danh sách flag chính xác theo tag, type, từ khóa tìm kiếm.
  20. `test_cross_org_flag_access_returns_404`: User Org A truy cập Flag Org B trả 404 Not Found.
  21. `test_viewer_role_cannot_modify_flag_or_settings_403`: Role VIEWER bị chặn 403 Forbidden khi ghi.
- **Definition of Done Verification**:
  - `pytest backend/app/tests/ -k flag -v`: **24 passed, 30 deselected (100%)**.
  - `make lint` (`ruff check .` + `mypy app`): **All checks passed! No issues found in 47 source files**.
  - Toàn bộ test suite dự án: **54 passed in 20.45s (100%)**.

## Known Issues
- Không có lỗi tồn đọng.
- Tầng evaluation engine và ruleset ETag phục vụ SDK sẽ kết nối trực tiếp vào các entity này ở Slice 5 & Slice 6.

## Dependencies
- Slice này phụ thuộc: S01 (Models), S02 (Auth & RBAC), S03 (Tenancy & Environment).
- Slice phụ thuộc slice này: S05 (Targeting Rules & Segments), S06 (Evaluation Engine & Ruleset ETag).
