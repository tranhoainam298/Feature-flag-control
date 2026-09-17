# Progress Report — Slice 11: Seed Data & Demo Web App

**Ngày hoàn thành:** 2026-09-17  
**Trạng thái:** HOÀN THÀNH (100% tiêu chí Definition of Done)  
**Kỹ năng áp dụng:** `python-fastapi-backend`, `python-sdk-design`, `ponytail`, `taste-skill`

---

## 1. Mục tiêu Slice 11

Slice 11 tạo dựng cơ sở dữ liệu mẫu phong phú, có tính thực tế cao cho việc bảo vệ đồ án / demo hội đồng, đồng thời phát triển ứng dụng web mẫu độc lập (`demo-app/`) chạy trên cổng 3001, tích hợp trực tiếp FlagOps Python SDK ở chế độ `in_process` (5s polling) để trình diễn các tính năng cốt lõi:
1. Đổi giao diện thời gian thực khi bật/tắt flag (`checkout-v2`) mà không cần restart server hay tải lại trang thủ công.
2. Hiển thị cấu hình runtime lấy từ Config Center (`payment.timeout_ms = 3000ms`, `payment.gateway = stripe`).
3. Sân chơi kiểm thử ngữ cảnh động (Context Evaluation Playground) với thời gian phản hồi micro-giây (< 0.1ms).
4. Mô phỏng phân phối xác suất 1.000 người dùng (Monte Carlo simulation) chứng minh thuật toán MurmurHash3 chuẩn xác.
5. Kiểm chứng khả năng chịu lỗi (Fail-safe Resilience): Tắt backend API, demo app vẫn phục vụ 200 OK và tiếp tục đánh giá từ in-memory cache.

---

## 2. Các cấu phần đã hiện thực

### 2.1. Phần A — Script Nạp Dữ Liệu Mẫu (`backend/app/seed.py`)
- Lệnh chạy: `python -m app.seed` hoặc `make seed`
- Hỗ trợ tham số `--reset` để xóa sạch dữ liệu demo trước đó và nạp lại.
- **Tính Idempotent**: Chạy nhiều lần liên tiếp không làm nhân đôi bản ghi hay gây lỗi xung đột khóa chính/unique.
- **Tập dữ liệu khởi tạo**:
  - **1 Organization**: `demo-org` ("Demo Organization")
  - **3 Users**:
    - `owner@demo.local` (Vai trò: `OWNER`, Mật khẩu: `demo1234`)
    - `dev@demo.local` (Vai trò: `DEVELOPER`, Mật khẩu: `demo1234`)
    - `viewer@demo.local` (Vai trò: `VIEWER`, Mật khẩu: `demo1234`)
  - **1 Project**: `demo-project` ("Demo Project")
  - **3 Environments**:
    - `dev` (Development, `is_production=False`)
    - `staging` (Staging, `is_production=False`)
    - `prod` (Production, `is_production=True`)
  - **6 API Keys** (2 key mỗi môi trường: 1 SERVER key, 1 CLIENT key):
    - `dev`: `fo_srv_dev_secret_key_demo_12345678`, `fo_cli_dev_client_key_demo_12345678`
    - `staging`: `fo_srv_staging_secret_key_demo_123456`, `fo_cli_staging_client_key_demo_123456`
    - `prod`: `fo_srv_prod_secret_key_demo_12345678`, `fo_cli_prod_client_key_demo_12345678`
  - **2 Segments**:
    - `vn-premium`: `country IN ["VN"] AND plan == "premium"`
    - `early-adopters`: `beta_tester == True OR signup_date <= "2026-01-01"`
  - **5 Feature Flags**:
    1. `checkout-v2`: Boolean, có targeting rule `country IN [VN] AND plan == premium -> ON`.
    2. `new-homepage`: Boolean, rollout 20% True / 80% False qua MurmurHash3 bucketing.
    3. `dark-mode`: Boolean, bật 100% ở `dev`, tắt ở `prod`.
    4. `payment-v2`: Multivariate 3 nhánh (`control` 34% / `variant_a` 33% / `variant_b` 33%).
    5. `recommendation-engine`: JSON flag mang cấu hình thuật toán gợi ý AI (`v1_collaborative` và `v2_deep_rank`).
  - **2 Config Namespaces & 6 Config Items**:
    - `payment-service`:
      - `payment.timeout_ms`: 3000 (INT)
      - `payment.stripe_secret_key`: Secret được mã hóa đối xứng AES-256-GCM.
      - `payment.gateway`: "stripe" (STRING)
    - `application`:
      - `app.maintenance_mode`: "false" (BOOL)
      - `app.max_upload_mb`: 50 (INT)
      - `app.rate_limit_per_min`: 100 (INT)
  - **3 Config Releases**: Trong namespace `payment-service` (v1: 1000ms, v2: 5000ms, v3: rollback về 3000ms có trường `is_rollback_of`).
  - **20 Audit Logs**: Ghi nhận đầy đủ lịch sử thao tác của các thực thể kèm diff JSON trước/sau, actor, địa chỉ IP và user agent.

### 2.2. Phần B — Demo Web App (`demo-app/`)
- Stack: Python 3.12 + FastAPI + Jinja2 + FlagOps Python SDK (`in_process` mode, 5s polling interval).
- Cổng dịch vụ: 3001.
- Thẩm mỹ giao diện (`taste-skill` anti-slop):
  - Theme dark-tech cao cấp (nền zinc-950 `#09090b`, thẻ zinc-900 `#18181b`, viền tinh tế `#27272a`).
  - Màu nhấn semantic: Emerald `#10b981` (sẵn sàng/bật), Amber `#f59e0b` (cảnh báo/degraded), Blue `#3b82f6` (thông tin).
  - Badge trạng thái thời gian thực: "● SDK Ready (In-Process)" vs "▲ SDK Degraded (Serving Cache)", version ruleset, đếm lùi chu kỳ sync 5s.
- **Kịch bản Demo Tự Động**:
  - Khi người dùng ở dashboard chuyển cờ `checkout-v2` từ False sang True (hoặc ngược lại), đoạn mã JS nền định kỳ 3 giây gọi `/api/status`, phát hiện thay đổi và hoán đổi giao diện checkout tức thì (< 10 giây) mà **không cần restart dịch vụ hay bấm F5**.
  - Trình diễn Checkout V2 (1-Click Express Buy / Apple Pay) vs Checkout Legacy (3-Step form dài).
  - Hiển thị giá trị cấu hình `payment.timeout_ms = 3000ms` đang được nạp từ Config Center.
  - Sân chơi đánh giá ngữ cảnh: Nhập `userId`, `country`, `plan` -> hiển thị ngay lập tức kết quả, biến thể, lý do đánh giá (`TARGETING_MATCH`, `DEFAULT`) và độ trễ (< 100 micro-giây).
  - Nút bấm mô phỏng 1.000 người dùng: Thực thi 1.000 lượt đánh giá in-memory, vẽ biểu đồ phân phối thanh ngang và bảng thống kê tỷ lệ phần trăm thực tế.

### 2.3. Phần C — Đóng Gói Docker Compose & Khả Năng Chịu Lỗi (Fail-Safe)
- Thêm dịch vụ `demo` vào `docker-compose.yml`, mount trên cổng `3001:3001`.
- Dockerfile tự động đóng gói mã nguồn FlagOps Python SDK từ thư mục `sdk/python`.
- **Xác minh kịch bản Backend Chết**:
  - Dừng container `flagops-api` (`docker compose stop api`).
  - Gọi lại `http://localhost:3001/` -> HTTP 200 OK.
  - Demo app tiếp tục phục vụ người dùng bình thường nhờ ruleset đã nạp sẵn trong cache RAM của SDK, hiển thị badge cảnh báo "SDK Degraded (Serving Cache)".
  - Bật lại `flagops-api` (`docker compose start api`) -> SDK tự động kết nối lại và chuyển trạng thái về "SDK Ready (In-Process)".

---

## 3. Bằng chứng kiểm thử & Xác minh

### 3.1. Kiểm thử Seed Script
```bash
docker compose exec -T api pytest app/tests/unit/test_seed.py -v
```
Kết quả:
- `test_seed_execution_and_verification`: **PASSED**
- `test_seed_idempotence`: **PASSED** (chạy lần 2 không tăng số lượng bản ghi)

### 3.2. Kiểm thử Demo Web App
```bash
python -m pytest demo-app/tests/ -v
```
Kết quả:
- `test_demo_home_page_returns_200`: **PASSED**
- `test_demo_evaluate_api`: **PASSED**
- `test_demo_simulate_1000_api`: **PASSED**
- `test_demo_status_api`: **PASSED**
- `test_demo_failsafe_when_backend_unreachable`: **PASSED**

### 3.3. Toàn bộ Bộ Kiểm thử Backend (214 tests)
```bash
docker compose exec -T api pytest
```
Kết quả: **214/214 passed** (100% xanh, không hồi quy).

### 3.4. Kiểm tra Linting & Type Checking
- `docker compose exec -T api ruff check .`: **All checks passed!**
- `docker compose exec -T api mypy app`: **Success: no issues found in 83 source files**

---

## 4. Hướng dẫn sử dụng Demo cho Hội Đồng / Video Bảo Vệ

1. **Khởi động toàn bộ cụm dịch vụ**:
   ```bash
   make up
   make migrate
   make seed
   ```
2. **Mở trình duyệt truy cập**:
   - Dashboard quản trị: `http://localhost:3000` (đăng nhập: `owner@demo.local` / `demo1234`)
   - Backend API Docs: `http://localhost:8000/docs`
   - Demo App khách hàng: `http://localhost:3001`
3. **Kịch bản Demo**:
   - **Bước 1**: Mở `http://localhost:3001`. Xem giao diện Checkout V2 đang bật cho tài khoản VN Premium.
   - **Bước 2**: Thử nghiệm tại "Context Evaluation Playground": chọn cờ `new-homepage` hoặc `payment-v2`, bấm "Evaluate Flag" để thấy độ trễ micro-giây.
   - **Bước 3**: Bấm "Run 1,000 In-Process Evaluations" để xem đồ thị phân phối tỷ lệ rollout thực tế (20/80 hoặc 34/33/33).
   - **Bước 4 (Đổi cờ runtime)**: Vào trang admin hoặc tắt cờ `checkout-v2` cho dev environment -> nhìn màn hình demo app chuyển sang giao diện Legacy trong < 10 giây mà không cần F5.
   - **Bước 5 (Fail-safe)**: Chạy `docker compose stop api` -> tải lại trang `http://localhost:3001/`, trang web vẫn hiển thị 200 OK mượt mà từ in-memory cache của SDK.
