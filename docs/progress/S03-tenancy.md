# S03: Tenancy & CRUD — Organization, Membership, Project, Environment, API Key

## Ngày hoàn thành
2026-09-16

## Implemented
- **Multi-Tenancy & Data Isolation (`backend/app/core/permissions.py`)**:
  - Xây dựng hệ thống dependency phân quyền và cô lập dữ liệu dùng chung:
    - `require_org_role(min_role)`: Xác thực quyền thành viên theo vai trò trong tổ chức.
    - `require_project_role(min_role)`: Xác thực quyền sở hữu dự án theo tổ chức của user.
    - `require_environment_role(min_role)`: Xác thực quyền môi trường xuyên suốt từ environment -> project -> organization.
    - `require_api_key_role(min_role)`: Xác thực quyền API key xuyên suốt api_key -> environment -> project -> organization.
  - **Quy tắc bảo mật cách ly dữ liệu**:
    - User thuộc Tổ chức A khi cố truy cập bất kỳ tài nguyên nào (Project, Environment, API Key) của Tổ chức B **luôn nhận về HTTP 404 Not Found** (tuyệt đối không trả 403 để chống rò rỉ sự tồn tại của tài nguyên chéo tenant).
    - User thuộc cùng tổ chức nhưng không đủ thẩm quyền theo vai trò (ví dụ: `VIEWER` tạo API Key) sẽ nhận về HTTP 403 Forbidden.
- **Quy tắc tạo Environment (`backend/app/services/tenancy.py`)**:
  - Khi tạo một `Project`, hệ thống tự động sinh 3 environments chuẩn:
    - `development`: key="development", name="Development", `is_production=False`, `ruleset_version=0`.
    - `staging`: key="staging", name="Staging", `is_production=False`, `ruleset_version=0`.
    - `production`: key="production", name="Production", `is_production=True`, `ruleset_version=0`.
- **Quản lý API Key bảo mật (`backend/app/services/tenancy.py`, `backend/app/api/v1/environments.py`, `backend/app/api/v1/api_keys.py`)**:
  - Tiền tố API Key: `fo_srv_` cho SERVER scope, `fo_cli_` cho CLIENT scope.
  - Sinh chuỗi ngẫu nhiên bằng `secrets.token_urlsafe(32)`.
  - Chỉ lưu `key_hash` (SHA-256) và `key_prefix` (12 ký tự đầu) vào cơ sở dữ liệu.
  - **Raw key CHỈ trả về đúng 1 lần trong response của POST tạo key**, các lần GET sau chỉ trả `key_prefix`.
  - Endpoint `POST /api/v1/api-keys/{id}/revoke`: Đánh dấu `revoked_at = utcnow()`, không xóa cứng. Khi gọi verify bằng key đã thu hồi sẽ trả về 401 Unauthorized.
  - Tạo API Key yêu cầu tối thiểu vai trò `DEVELOPER` (`VIEWER` bị chặn với 403).
- **CRUD Endpoints & Routers (`backend/app/api/v1/`)**:
  - `organizations.py`:
    - `POST /api/v1/organizations`: Tạo tổ chức mới, gán người tạo làm `OWNER`.
    - `GET /api/v1/organizations`: Danh sách tổ chức của user hiện tại.
    - `GET /api/v1/organizations/{org_id}`: Chi tiết tổ chức.
    - `PATCH /api/v1/organizations/{org_id}`: Cập nhật thông tin tổ chức.
    - `DELETE /api/v1/organizations/{org_id}`: Xóa tổ chức (CASCADE).
    - `GET /api/v1/organizations/{org_id}/members`: Danh sách thành viên.
    - `POST /api/v1/organizations/{org_id}/members`: Thêm thành viên mới.
    - `PATCH /api/v1/organizations/{org_id}/members/{user_id}`: Sửa vai trò thành viên (chặn hạ quyền Owner cuối cùng).
    - `DELETE /api/v1/organizations/{org_id}/members/{user_id}`: Xóa thành viên (chặn xóa Owner cuối cùng).
    - `GET /api/v1/organizations/{org_id}/projects`: Danh sách project trong tổ chức (tổ chức mới tạo có danh sách project rỗng).
    - `POST /api/v1/organizations/{org_id}/projects`: Tạo project mới kèm 3 environment tự động.
  - `projects.py`:
    - `GET /api/v1/projects/{project_id}`: Chi tiết project (cách ly org 404).
    - `PATCH /api/v1/projects/{project_id}`: Sửa project.
    - `DELETE /api/v1/projects/{project_id}`: Xóa project.
    - `GET /api/v1/projects/{project_id}/environments`: Danh sách environment của project.
    - `POST /api/v1/projects/{project_id}/environments`: Tạo thêm environment.
  - `environments.py`:
    - `GET /api/v1/environments/{environment_id}`: Chi tiết environment.
    - `PATCH /api/v1/environments/{environment_id}`: Sửa environment.
    - `DELETE /api/v1/environments/{environment_id}`: Xóa environment.
    - `GET /api/v1/environments/{environment_id}/api-keys`: Danh sách API key (chỉ có prefix).
    - `POST /api/v1/environments/{environment_id}/api-keys`: Tạo API key mới.
  - `api_keys.py`:
    - `POST /api/v1/api-keys/{api_key_id}/revoke`: Thu hồi API key.

## Tests & Definition of Done
- **Bộ kiểm thử tự động tại `backend/app/tests/test_tenancy.py`**:
  1. `test_create_org_has_empty_projects`: Tạo org mới có danh sách project rỗng.
  2. `test_create_project_auto_generates_three_environments`: Tạo project tự động sinh 3 environment (dev, staging, prod với `is_production=True`).
  3. `test_create_apikey_returns_raw_key`: Tạo API key trả về raw key (bắt đầu bằng `fo_srv_` hoặc `fo_cli_`).
  4. `test_get_apikey_list_does_not_contain_raw_key`: GET API key list chỉ chứa `key_prefix`, không có `key` hay `key_hash`.
  5. `test_revoke_apikey_returns_401_on_verification`: Thu hồi key thành công, gọi lại bằng key đó trả về 401.
  6. `test_user_org_a_get_project_org_b_returns_404`: User Org A truy cập Project Org B trả về 404 Not Found (chống rò rỉ dữ liệu).
  7. `test_viewer_create_apikey_returns_403`: Role VIEWER cố tạo API key nhận 403 Forbidden.
  8. `test_environment_crud_and_cross_org_isolation`: Thao tác environment và kiểm tra cách ly chéo tổ chức trả về 404.
  9. `test_duplicate_org_and_project_slug_conflict_409`: Xử lý trùng lặp slug trả về 409 Conflict.
- **Definition of Done Verification**:
  - Lệnh kiểm tra: `pytest backend/app/tests/ -k "org or project or environment or apikey" -v`
  - Kết quả: **11 passed, 22 deselected (100%)**.
  - Kiểm tra toàn bộ test suite: **33 passed in 9.22s (100%)**.
  - Kiểm tra Linter & Type Check: `ruff check app` -> **All checks passed!**, `mypy app` -> **Success: no issues found in 43 source files**.

## Known Issues
- Không có lỗi tồn đọng.
- Hệ thống cách ly multi-tenancy hoạt động đúng thiết kế và quy chuẩn an toàn.

## Dependencies
- Slice này phụ thuộc: S01 (Database Models), S02 (Auth & RBAC).
- Slice phụ thuộc slice này: S04 (CRUD Flag + Variations, liên kết Project & Environment), S05 (Evaluation & API Key Verification).
