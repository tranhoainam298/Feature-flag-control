# Workflow — Quy trình làm việc FlagOps

## Quy trình 7 bước cho mỗi task

### 1. Inspect — Khảo sát
- Đọc code liên quan, hiểu ngữ cảnh hiện tại
- Xác định file nào cần sửa, file nào cần tạo mới
- Kiểm tra test hiện có còn xanh không: `make test`

### 2. Decide — Quyết định
- Chọn phương án triển khai
- Nếu là quyết định kiến trúc → viết ADR trước khi code

### 3. Implement — Triển khai
- Viết code theo skill tương ứng (nạp skill trước khi viết)
- Tuân thủ cây thư mục và quy tắc phân tầng
- Commit thường xuyên, Conventional Commits

### 4. Test — Viết test
- Viết test TRƯỚC hoặc NGAY SAU khi implement
- Engine: ≥ 95% coverage. Services: ≥ 80%. Tổng: ≥ 75%
- Không viết test giả (`assert True`)

### 5. Fix — Sửa lỗi
- Chạy `make lint` → fix tất cả warning/error
- Chạy `make test` → fix tất cả test đỏ
- Kiểm tra test của slice TRƯỚC có bị phá không

### 6. Verify — Xác minh
- Chạy lại toàn bộ test suite: `make test`
- Kiểm tra endpoint bằng curl/httpie nếu là API
- Kiểm tra UI trên trình duyệt nếu là frontend

### 7. Progress note — Ghi tiến độ
- Cập nhật `docs/progress/SXX-ten.md`
- Đánh dấu task đã xong trong backlog
- Nếu kết thúc slice → tạo file progress mới
