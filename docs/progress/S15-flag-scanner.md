# S15: Flag Scanner CLI (Điểm khác biệt học thuật số 2)

## Ngày hoàn thành
2026-09-17

## Kỹ năng áp dụng
`flagops-architecture`, `python-testing-pytest`, `ponytail`, `tdd`, `docs-adr-progress`

---

## 1. Tổng quan Slice 15

Xây dựng **`tools/flag-scanner/`** — công cụ dòng lệnh (CLI) Python độc lập để phân tích cú pháp tĩnh mã nguồn dự án, phát hiện các lệnh gọi đánh giá feature flag, đối chiếu với FlagOps Server, phát hiện nợ kỹ thuật (DEAD, STALE, UNDECLARED, ORPHAN), xuất báo cáo đa định dạng (text, json, markdown) và làm chốt chặn tự động cho quy trình CI/CD (`--fail-on-dead`).

---

## 2. Kiến trúc & Tính năng Kỹ thuật

### 2.1. Phân tích Cú pháp AST (Python) & Regex Ràng buộc (Đa ngôn ngữ)
- **Python AST Parser (`flag_scanner/scanner/ast_parser.py`)**:
  - Tận dụng thư viện chuẩn `ast` của Python với `NodeVisitor`.
  - Phân tích cây cú pháp trừu tượng, tìm kiếm chính xác các lời gọi SDK:
    - `client.is_enabled("key")`
    - `client.get_boolean("key")`
    - `client.get_string("key")`
    - `client.get_number("key")`
    - `client.get_json("key")`
    - `client.get_variant("key")`
    - `client.get_evaluation("key")`
  - Bắt trọn vẹn các lời gọi lồng sâu trong hàm, phương thức lớp (class), khối `if/else`, vòng lặp `for/while`, khối `try/except`.
  - **Kháng nhiễu tuyệt đối**: Bỏ qua chuỗi trong comment (`# ...`, docstring) và các biến gán chuỗi thông thường không phải là lời gọi SDK.
  - **Khả năng chịu lỗi cao**: Tự động bắt `SyntaxError` và `UnicodeDecodeError`, bỏ qua file lỗi cú pháp một cách êm đẹp mà không làm sập tiến trình quét.
- **Regex Scanner có ràng buộc (`flag_scanner/scanner/regex_scanner.py`)**:
  - Hỗ trợ các ngôn ngữ khác: `.js`, `.ts`, `.tsx`, `.jsx`, `.java`, `.go`, `.json`, `.yaml`, `.yml`.
  - Loại bỏ comment đơn dòng (`// ...`) và comment nhiều dòng (`/* ... */`) trước khi match pattern.
  - Ràng buộc tiền tố phương thức SDK (`isEnabled`, `getBooleanValue`, `getStringValue`, v.v.), không bao giờ match chuỗi ngẫu nhiên.
- **Bộ duyệt thư mục (`flag_scanner/scanner/walker.py`)**:
  - Bỏ qua các thư mục hệ thống: `.git`, `node_modules`, `__pycache__`, `venv`, `.venv`, `dist`, `build`.
  - Tự động đọc và tôn trọng các mẫu loại trừ trong `.gitignore`.

### 2.2. Đối chiếu Trạng thái với Server (Reconciliation)
- **Endpoint hỗ trợ (`GET /eval/v1/flag-health`)**:
  - Bổ sung vào `backend/app/api/eval/router.py`, cho phép xác thực bằng `X-FlagOps-Key` (API key của môi trường SDK) để lấy toàn bộ danh sách cờ, trạng thái vòng đời và điểm nợ kỹ thuật của project.
- **Bộ phân loại 5 trạng thái (`flag_scanner/reconciler.py`)**:
  - `DEAD`: Cờ đã `ARCHIVED` trên server nhưng vẫn còn tồn tại trong mã nguồn $\rightarrow$ Khuyến nghị xóa ngay nhánh điều kiện.
  - `STALE`: Cờ có `debt_score >= 60` hoặc trạng thái `STALE` $\rightarrow$ Khuyến nghị hoàn tất rollout và dọn dẹp code.
  - `UNDECLARED`: Cờ có trong mã nguồn nhưng không tồn tại trên server $\rightarrow$ Cảnh báo gõ sai key hoặc chưa tạo cờ.
  - `ORPHAN`: Cờ có trên server nhưng không tìm thấy vị trí nào trong mã nguồn $\rightarrow$ Đề xuất archive cờ trên server.
  - `OK`: Cờ đang hoạt động bình thường trên cả server và mã nguồn.
  - Hỗ trợ chế độ offline khi mất kết nối mạng hoặc không có API key.

### 2.3. Giao diện Dòng lệnh (CLI) & Báo cáo
- **Lệnh `flag-scanner scan <path>`**:
  - `--api-url`: Địa chỉ server FlagOps.
  - `--api-key`: API key xác thực.
  - `--format`: `text` (mặc định), `json`, `markdown`.
  - `--fail-on-dead`: Trả về mã thoát 1 (exit code 1) nếu phát hiện bất kỳ cờ `DEAD` nào, thích hợp tích hợp vào GitHub Actions / GitLab CI.
  - `--output`: Xuất kết quả ra file chỉ định.
- **Lệnh `flag-scanner report --output report.md`**:
  - Tạo báo cáo Markdown chi tiết kèm bảng tổng quan và snippet vị trí từng dòng code.
- **Lệnh `flag-scanner init`**:
  - Khởi tạo file cấu hình `.flagscanner.toml` mẫu trong dự án.

---

## 3. Kết quả Thực thi Thực tế & Kiểm thử

### 3.1. Chạy Quét Thực tế trên `./demo-app`
```bash
flag-scanner scan ./demo-app --api-url http://localhost:8000 --api-key fo_srv_dev_secret_key_demo_12345678
```

**Output thu được**:
```text
Flag: dark-mode
Status: ORPHAN
Occurrences: 0
Recommendation: Flag có trên server nhưng không tìm thấy trong code, có thể cân nhắc archive

Flag: new-homepage
Status: ORPHAN
Occurrences: 0
Recommendation: Flag có trên server nhưng không tìm thấy trong code, có thể cân nhắc archive

Flag: payment-v2
Status: ORPHAN
Occurrences: 0
Recommendation: Flag có trên server nhưng không tìm thấy trong code, có thể cân nhắc archive

Flag: recommendation-engine
Status: ORPHAN
Occurrences: 0
Recommendation: Flag có trên server nhưng không tìm thấy trong code, có thể cân nhắc archive

Flag: checkout-v2
Status: OK
Occurrences: 3
Files:
    D:\python\feature flag\demo-app\main.py:93
    D:\python\feature flag\demo-app\main.py:97
    D:\python\feature flag\demo-app\main.py:198
Recommendation: Cờ tính năng đang hoạt động bình thường

Tổng kết: 1 flag trong code, 0 DEAD, 0 STALE, 0 UNDECLARED, 4 ORPHAN, 1 OK
```

### 3.2. Chạy Quét trên Fixture Project (Có cả Python, TypeScript, File lỗi cú pháp, Comment decoy)
```bash
flag-scanner scan ./tools/flag-scanner/tests/fixtures/sample-project --api-url http://localhost:8000 --api-key fo_srv_dev_secret_key_demo_12345678
```

**Output thu được**:
```text
Flag: dead-feature-flag
Status: UNDECLARED
Occurrences: 1
Files:
    D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\app.py:27
Recommendation: Flag chưa được khai báo trên server hoặc có thể gõ sai tên key

Flag: recommendation-engine
Status: ORPHAN
Occurrences: 0
Recommendation: Flag có trên server nhưng không tìm thấy trong code, có thể cân nhắc archive

Flag: checkout-v2
Status: OK
Occurrences: 2
Files:
    D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\app.py:11
    D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\service.ts:9
Recommendation: Cờ tính năng đang hoạt động bình thường

Flag: dark-mode
Status: OK
Occurrences: 1
Files:
    D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\service.ts:14
Recommendation: Cờ tính năng đang hoạt động bình thường

Flag: new-homepage
Status: OK
Occurrences: 1
Files:
    D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\app.py:15
Recommendation: Cờ tính năng đang hoạt động bình thường

Flag: payment-v2
Status: OK
Occurrences: 2
Files:
    D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\app.py:24
    D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\service.ts:16
Recommendation: Cờ tính năng đang hoạt động bình thường

Tổng kết: 5 flag trong code, 0 DEAD, 0 STALE, 1 UNDECLARED, 1 ORPHAN, 4 OK
```

### 3.3. Kết quả Test Tự động
```bash
python -m pytest tools/flag-scanner/tests -v
```
**21/21 passed in 0.46s (100% Pass)**

Kiểm tra toàn bộ backend suite:
- Unit tests: **149/149 passed**
- Integration tests: **3/3 passed**
