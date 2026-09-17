# S14: Flag Lifecycle & Technical Debt Score

## Ngày hoàn thành
2026-09-17

## Kỹ năng áp dụng
`python-fastapi-backend`, `python-testing-pytest`, `flagops-architecture`, `ponytail`, `tdd`, `frontend-react-dashboard`, `taste-skill`, `web-design-guidelines`, `docs-adr-progress`

---

## 1. Mục tiêu Slice 14 (Điểm khác biệt học thuật #1 của đồ án)

Hiện thực hóa máy trạng thái vòng đời cờ tính năng (Lifecycle State Machine), công thức tính điểm nợ kỹ thuật (Technical Debt Score) thuần khiết (pure engine), hệ thống khuyến nghị hành động, API Flag Health, và Giao diện Dashboard quản trị sức khỏe cờ:
- **Máy trạng thái vòng đời**: `DRAFT` → `ACTIVE` → `ROLLED_OUT` → `STALE` → `ARCHIVED`. Trạng thái được suy diễn động từ cấu hình thực tế thay vì lưu cứng.
- **Pure Debt Score Engine**: Mô-đun Python độc lập `flag_debt.py`, không I/O, không truy cập DB hay mạng, tính toán điểm số từ 0–100 dựa trên 4 thành phần trọng số.
- **Khuyến nghị dọn dẹp**: Tự động sinh danh sách hành động đề xuất cụ thể (gỡ code thừa khỏi repo, archive cờ cũ, hoàn tất rollout).
- **Flag Health API**: Endpoints xem danh sách sức khỏe toàn dự án, xem chi tiết từng cờ, và thực hiện archive cờ (kèm ghi audit log).
- **Frontend Dashboard**: Trang `/health` hiển thị KPI tổng hợp, bảng trực quan hóa tiến trình điểm nợ, lọc trạng thái, và modal xác nhận archive.

---

## 2. Các cấu phần đã hiện thực (Implemented)

### 2.1. Backend Pure Engine & Domain Models
- **`backend/app/models/enums.py`**:
  - Bổ sung enum `LifecycleState`: `DRAFT`, `ACTIVE`, `ROLLED_OUT`, `STALE`, `ARCHIVED`.
- **`backend/app/core/config.py`**:
  - Bổ sung 4 trọng số điểm nợ kỹ thuật:
    - `DEBT_W_AGE = 0.25`: Trọng số tuổi thọ cờ.
    - `DEBT_W_ROLLOUT = 0.35`: Trọng số thời gian duy trì ở mức 100% rollout.
    - `DEBT_W_STALENESS = 0.25`: Trọng số thời gian không có lượt đánh giá (evaluation).
    - `DEBT_W_TEMPORARY = 0.15`: Trọng số penalty đối với cờ tạm thời quá hạn.
- **`backend/app/services/flag_debt.py`**:
  - `DebtWeights`: Dataclass chứa các trọng số.
  - `FlagSnapshot`: Dataclass đóng gói dữ liệu thô phục vụ tính toán.
  - `DebtResult`: Dataclass chứa điểm số tổng (0–100), trạng thái vòng đời, breakdown 4 thành phần và danh sách khuyến nghị.
  - `derive_lifecycle_state(snapshot)`: Hàm suy diễn trạng thái theo logic chặt chẽ.
  - `calculate_debt_score(snapshot, weights)`: Hàm tính điểm thuần túy.
  - `get_recommendations(state, snapshot)`: Hàm sinh chuỗi khuyến nghị tiếng Việt.

### 2.2. Backend I/O Service & API Layer
- **`backend/app/schemas/flag_health.py`**:
  - `FlagHealthResponse`: Schema trả về chi tiết sức khỏe từng cờ.
  - `FlagHealthSummary`: Schema tóm tắt số liệu toàn dự án (tổng, draft, active, rolled_out, stale, archived, avg_score).
  - `FlagHealthListResponse`: Schema danh sách và tổng quan.
- **`backend/app/services/flag_health.py`**:
  - `get_flag_health_list`: Truy vấn thông tin các cờ thuộc project, tổng hợp `FlagSnapshot` và tính toán điểm nợ song song.
  - `get_single_flag_health`: Lấy chi tiết sức khỏe của 1 cờ.
  - `archive_flag`: Đánh dấu cờ thành `archived_at=now()`, ngăn chặn archive trùng lặp (409 Conflict), ghi nhận `AuditLog` với `action="flag.archived"`.
- **`backend/app/api/v1/flag_health.py`**:
  - Định tuyến các endpoints:
    - `GET /api/v1/projects/{project_id}/flag-health`
    - `GET /api/v1/projects/{project_id}/flags/{flag_id}/health`
    - `POST /api/v1/projects/{project_id}/flags/{flag_id}/archive`
  - Đăng ký router trong `backend/app/main.py`.

### 2.3. Frontend Dashboard & UI Components
- **`frontend/src/types/health.ts` & `index.ts`**:
  - Định nghĩa TypeScript interfaces `LifecycleState`, `FlagHealthItem`, `FlagHealthSummary`, `FlagHealthListResponse`.
- **`frontend/src/features/flags/api.ts`**:
  - Bổ sung `listFlagHealth`, `getFlagHealth`, `archiveFlagByHealth`.
- **`frontend/src/features/flags/FlagHealthBadge.tsx`**:
  - Component hiển thị huy hiệu trạng thái vòng đời với icon và bảng màu chuẩn: DRAFT (xám), ACTIVE (xanh ngọc), ROLLED_OUT (xanh dương), STALE (vàng hổ phách), ARCHIVED (đỏ nhạt).
- **`frontend/src/pages/FlagHealthPage.tsx`**:
  - Bố cục quản trị chuẩn `taste-skill` mật độ cao:
    - 7 thẻ KPI tổng quát trên đầu trang.
    - Thanh công cụ tìm kiếm và lọc trạng thái thời gian thực.
    - Bảng hiển thị cờ, trạng thái, thanh tiến trình điểm nợ đổi màu (Xanh < 30, Vàng 30-60, Đỏ > 60), chỉ số breakdown chi tiết (Tuổi, Rollout, Cũ, Tạm).
    - Cột đề xuất hành động thực tiễn.
    - Nút Archive kích hoạt Modal xác nhận an toàn.
- **`frontend/src/components/Sidebar.tsx` & `App.tsx`**:
  - Bổ sung điều hướng "Flag Health & Debt" với icon `HeartPulse` và route `/health`.
  - Tích hợp `FlagHealthBadge` trực tiếp vào `FlagHeader.tsx`.

---

## 3. Kết quả Kiểm thử & Xác minh (Verification)

| Hạng mục kiểm thử | Lệnh thực thi | Kết quả |
|---|---|---|
| **Flag Debt Unit Tests** | `python -m pytest app/tests/unit/test_flag_debt.py -v` | **27/27 passed** (100%) |
| **Backend Unit Suite** | `python -m pytest app/tests/unit -v` | **149/149 passed** (0 failures) |
| **API Integration Tests** | `python -m pytest app/tests/integration/test_flag_health_api.py -v` | **3/3 passed** (100%) |
| **Frontend TypeScript & Build** | `npm run build` | **0 errors** (vite built in 3.39s) |
| **Browser E2E Verification** | `browser_subagent` session recording | **Đạt** (Đăng nhập, duyệt KPI, lọc, mở modal archive) |
