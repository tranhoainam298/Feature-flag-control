# S16: Change Request — Kiểm soát Thay đổi & Nguyên tắc Bốn Mắt

## Ngày hoàn thành
2026-09-17

## Kỹ năng áp dụng
`python-fastapi-backend`, `api-contract-rest`, `security-hardening`, `ponytail`, `docs-adr-progress`

---

## 1. Mục tiêu Slice 16

Hiện thực hóa quy trình kiểm soát thay đổi (Change Request) cho môi trường Production, bảo đảm an toàn vận hành hệ thống thông qua:
- **Chặn sửa trực tiếp trên Production**: Khi `environment.is_production = True`, mọi thao tác cập nhật cấu hình cờ hoặc quy tắc targeting không áp dụng trực tiếp mà tự động tạo Change Request ở trạng thái `PENDING` (trả về HTTP 202 Accepted). Môi trường non-production (`dev`, `staging`) áp dụng ngay lập tức.
- **Máy trạng thái Change Request**: `DRAFT` → `PENDING` → `APPROVED` → `APPLIED`, hoặc `REJECTED` / `CANCELLED`.
- **Nguyên tắc bốn mắt (Four-Eyes Principle)**: Người tạo (`requested_by`) tuyệt đối không được tự duyệt Change Request của chính mình. Nếu cố tình tự duyệt, API trả về HTTP 403 với mã lỗi chuẩn `SELF_APPROVAL_FORBIDDEN`.
- **Phân quyền duyệt**: Chỉ người dùng có vai trò `ADMIN` hoặc `OWNER` mới có quyền duyệt hoặc từ chối Change Request.
- **Mô phỏng tác động (/impact) — Điểm khác biệt học thuật & công nghệ**:
  - Trích xuất tối đa 1,000 context đánh giá gần nhất từ bảng `evaluation_event`.
  - Chạy `evaluate()` của pure evaluation engine 2 lần hoàn toàn trong bộ nhớ (với ruleset hiện tại và ruleset giả lập sau thay đổi) mà không cần ghi DB.
  - Phân tích số lượng và tỉ lệ % người dùng bị ảnh hưởng, tổng hợp bảng ma trận chuyển dịch variation (từ variation X sang variation Y bao nhiêu lượt).
- **Hẹn giờ áp dụng (Scheduled Change)**:
  - Hỗ trợ trường `scheduled_at`. Background worker (APScheduler) quét định kỳ mỗi phút, tự động áp dụng các Change Request đã `APPROVED` khi đến hạn.
  - Ghi nhận Audit Log với `actor_id = None` và `action = "change_request.applied_by_scheduler"`.
- **Thực thi payload nguyên tử (Atomic Transaction)**:
  - Khi `APPLIED`, toàn bộ tập thay đổi trong payload JSONB được thực thi trong một transaction duy nhất.
  - Nếu xảy ra lỗi giữa chừng: tự động rollback toàn bộ, giữ Change Request ở trạng thái `APPROVED`, ghi log lỗi chi tiết.
- **Giao diện Quản trị**:
  - Trang `/change-requests` cho phép lọc theo môi trường và trạng thái, xem chi tiết diff payload, chạy mô phỏng tác động trực quan, cùng các nút thao tác Duyệt/Từ chối thông minh (tự động vô hiệu hóa nếu vi phạm nguyên tắc bốn mắt).

---

## 2. Các cấu phần đã hiện thực (Implemented)

### 2.1. Cơ sở dữ liệu & Migrations
- **`backend/alembic/versions/003_evaluation_event_context.py`**:
  - Thêm cột `context` (JSONB, nullable) vào bảng partitioned `evaluation_event` để lưu trữ thuộc tính context thực tế phục vụ mô phỏng tác động.
- **`backend/app/models/evaluation.py`**:
  - Cập nhật model `EvaluationEvent` thêm trường `context: Mapped[dict | None]`.
- **`backend/app/models/change_request.py` & `enums.py`**:
  - Bảng `change_request` với các cột: `id`, `environment_id`, `title`, `description`, `payload` (JSONB), `status` (Enum), `requested_by`, `reviewed_by`, `scheduled_at`, `applied_at`, `created_at`, `updated_at`.

### 2.2. Backend Services & Schemas
- **`backend/app/schemas/change_request.py`**:
  - `ChangeRequestCreate`: Schema tạo yêu cầu thay đổi.
  - `ChangeRequestResponse`: Schema chi tiết yêu cầu thay đổi.
  - `ImpactTransition`: Schema chuyển dịch variation (`from_variation`, `to_variation`, `count`).
  - `ChangeRequestImpactResponse`: Schema kết quả mô phỏng tác động (`total_contexts`, `affected_contexts`, `change_percentage`, `transitions`, `summary`, `flag_key`).
- **`backend/app/core/permissions.py`**:
  - Thêm dependency `require_change_request_role(min_role)`: Bảo đảm cô lập đa người thuê (cross-org trả về 404 thay vì 403) và kiểm tra role trong tổ chức.
- **`backend/app/services/change_request.py`**:
  - `list_change_requests`: Lọc danh sách theo environment và trạng thái.
  - `create_change_request`: Tạo CR, ghi nhận audit log `change_request.create`.
  - `approve_change_request`:
    - Kiểm tra người tạo tự duyệt → ném lỗi `SELF_APPROVAL_FORBIDDEN` (403).
    - Xử lý hẹn giờ tương lai (`APPROVED`) hoặc thực thi ngay (`APPLIED`).
  - `reject_change_request`: Chuyển trạng thái sang `REJECTED`, không áp dụng thay đổi.
  - `cancel_change_request`: Người tạo hoặc Admin hủy yêu cầu (`CANCELLED`).
  - `simulate_impact`: Đọc 1000 context gần nhất, dựng ruleset giả lập in-memory, gọi engine pure 2 lần và tính toán ma trận chuyển dịch.
  - `apply_payload`: Thực thi thay đổi setting/targeting rule trong 1 transaction, tăng `ruleset_version`, xóa cache Redis, rollback an toàn khi lỗi.
  - `process_scheduled_change_requests`: Quét và áp dụng CR đến hạn với `actor_id = None`.
- **`backend/app/services/flag.py` & `api/v1/flags.py`**:
  - Chặn sửa cờ trên môi trường Production: Tự động sinh `ChangeRequest` ở trạng thái `PENDING` và trả về HTTP 202.
- **`backend/app/api/v1/targeting.py`**:
  - Chặn sửa quy tắc targeting trên Production: Tự động sinh `ChangeRequest` PENDING và trả về HTTP 202.

### 2.3. API Endpoints
- `POST   /api/v1/environments/{e}/change-requests`
- `GET    /api/v1/environments/{e}/change-requests` (lọc theo status)
- `GET    /api/v1/change-requests/{c}`
- `GET    /api/v1/change-requests/{c}/impact`
- `POST   /api/v1/change-requests/{c}/approve`
- `POST   /api/v1/change-requests/{c}/reject`
- `POST   /api/v1/change-requests/{c}/cancel`

### 2.4. Background Scheduler
- **`backend/app/core/scheduler.py`**:
  - Khởi tạo `AsyncIOScheduler` chạy ngầm mỗi phút trong vòng đời FastAPI (`lifespan`), tự động kích hoạt `process_scheduled_change_requests`.

### 2.5. Frontend UI
- **`frontend/src/types/change_request.ts` & `index.ts`**:
  - Định nghĩa đầy đủ kiểu dữ liệu TypeScript.
- **`frontend/src/features/change_requests/api.ts`**:
  - Client gọi các API change-requests và impact.
- **`frontend/src/features/change_requests/ChangeRequestDetailModal.tsx`**:
  - Modal xem chi tiết CR:
    - Banner cảnh báo nguyên tắc bốn mắt khi người dùng đăng nhập là người tạo.
    - Trực quan hóa payload JSON diff.
    - Khối "Mô phỏng tác động": Hiển thị tổng context, số lượng thay đổi, tỉ lệ %, ma trận chuyển dịch badge và nút "Chạy lại mô phỏng".
    - Các nút Duyệt/Từ chối/Hủy với phân quyền và validation chặt chẽ.
- **`frontend/src/pages/ChangeRequestsPage.tsx`**:
  - Trang quản trị danh sách Change Request với thanh lọc trạng thái (Tabs), ô tìm kiếm, thông báo môi trường Production được bảo vệ.
- **`frontend/src/App.tsx` & `components/Sidebar.tsx`**:
  - Đăng ký route `/change-requests` và biểu tượng `GitPullRequest` trên thanh điều hướng.

---

## 3. Kết quả Kiểm thử & Nghiệm thu (Verification)

### 3.1. Bộ test tự động (Pytest)
Đã chạy toàn bộ 9 ca test bắt buộc tại `backend/app/tests/test_change_request.py`:

```
backend/app/tests/test_change_request.py::test_modify_flag_in_production_creates_pending_cr PASSED
backend/app/tests/test_change_request.py::test_modify_flag_in_dev_applies_immediately PASSED
backend/app/tests/test_change_request.py::test_self_approval_forbidden_403 PASSED
backend/app/tests/test_change_request.py::test_developer_approval_forbidden_403 PASSED
backend/app/tests/test_change_request.py::test_other_user_approves_applies_and_increments_ruleset_version PASSED
backend/app/tests/test_change_request.py::test_reject_change_request PASSED
backend/app/tests/test_change_request.py::test_impact_simulation_calculation PASSED
backend/app/tests/test_change_request.py::test_scheduled_change_applied_by_scheduler PASSED
backend/app/tests/test_change_request.py::test_payload_execution_failure_rollback PASSED

=================== 9 passed in backend/app/tests/test_change_request.py ===================
```

### 3.2. Demo thực tế 2 tài khoản (Developer → Owner)
Kịch bản demo được kiểm chứng trực tiếp qua script `backend/scripts/demo_slice16.py`:
1. `dev@demo.local` đăng nhập, sửa cờ `checkout-v2` trên `Production`.
2. Hệ thống chặn thay đổi trực tiếp, tạo Change Request `PENDING` (status code 202), giá trị cờ thực tế giữ nguyên `enabled = True`.
3. `dev@demo.local` cố tình tự duyệt → Hệ thống chặn với 403 `SELF_APPROVAL_FORBIDDEN`.
4. `owner@demo.local` đăng nhập, chạy mô phỏng tác động `/impact`.
5. `owner@demo.local` phê duyệt Change Request → Trạng thái chuyển `APPLIED`, cờ trên `Production` chuyển thành `enabled = False`.
