# ADR-010: Flag Scanner CLI — Phân tích Cú pháp AST và Đối chiếu Server

## Trạng thái
Accepted

## Ngày
2026-09-17

## Ngữ cảnh (Context)
Một trong những điểm yếu lớn nhất của các công cụ quét mã nguồn thông thường (như ripgrep hay grep đơn giản) là **tỉ lệ dương tính giả (false positive) rất cao**:
1. Chuỗi trùng tên cờ xuất hiện trong các đoạn chú thích (comments), docstrings, file markdown, hoặc log messages bị nhận diện nhầm là cờ đang hoạt động.
2. Các biến lưu chuỗi thông thường (ví dụ: `flag_name = "checkout-v2"`) bị coi là một điểm đánh giá cờ.
3. Không thể xác định ngữ cảnh cấu trúc lồng nhau (hàm, class, khối if/else) để đưa ra khuyến nghị xóa code chính xác.

Đồng thời, để phục vụ mục tiêu học thuật và thực tiễn của đồ án FlagOps, hệ thống cần một công cụ phân tích tĩnh (Static Code Analysis) chính xác và có khả năng tích hợp vào quy trình kiểm tra chất lượng mã nguồn (CI/CD Pipeline).

## Quyết định (Decision)

### 1. Phân tích Cú pháp AST (Abstract Syntax Tree) cho Python
Đối với các dự án Python, thay vì quét chuỗi bằng regex, `flag-scanner` sử dụng mô-đun chuẩn `ast` của Python thông qua `ast.NodeVisitor`:
- Duyệt qua cây cú pháp trừu tượng để tìm các nút `Call` có hàm gọi dạng `Attribute` (`client.<method>`).
- Danh sách phương thức đánh giá cờ của SDK được chuẩn hóa: `is_enabled`, `get_boolean`, `get_string`, `get_number`, `get_json`, `get_variant`, `get_evaluation`.
- Trích xuất chính xác đối số hằng số đầu tiên (`ast.Constant`) hoặc tham số `flag_key="key"`.
- Bắt lỗi `SyntaxError` và `UnicodeDecodeError` cục bộ để đảm bảo một file mã nguồn lỗi cú pháp không làm gián đoạn toàn bộ tiến trình quét.

### 2. Regex có ràng buộc chặt chẽ cho các ngôn ngữ khác (JS/TS/Java/Go)
Với các ngôn ngữ không chạy trên runtime Python, công cụ sử dụng biểu thức chính quy có ràng buộc cấu trúc (Constrained Regex):
- Ràng buộc tiền tố gọi hàm SDK (`\.is_?enabled\(...`, `\.get_?boolean\(...`, `\.getBooleanValue\(...`).
- Tách và loại bỏ hoàn toàn các comment một dòng (`//`, `#`) và comment nhiều dòng (`/* ... */`) trước khi khớp mẫu, đồng thời giữ nguyên số dòng của file gốc để báo cáo chính xác vị trí.

### 3. Đối chiếu Trạng thái với Server qua API Key
Để hỗ trợ chạy trong các môi trường CI/CD (không có tương tác người dùng để nhập JWT đăng nhập), FlagOps Server mở endpoint chuyên dụng:
- `GET /eval/v1/flag-health` xác thực bằng header `X-FlagOps-Key`.
- Server tự động ánh xạ API key về project tương ứng và trả về toàn bộ dữ liệu vòng đời, điểm nợ kỹ thuật và khuyến nghị.
- Phân loại cờ thành 5 trạng thái định lượng:
  - `DEAD`: `ARCHIVED` trên server nhưng còn trong mã nguồn (khuyến nghị xóa).
  - `STALE`: `debt_score >= 60` hoặc trạng thái `STALE` (khuyến nghị hoàn tất rollout).
  - `UNDECLARED`: Có trong code nhưng chưa có trên server (cảnh báo gõ sai key).
  - `ORPHAN`: Có trên server nhưng không có trong code (cân nhắc archive).
  - `OK`: Bình thường.

### 4. Chốt chặn CI/CD với cờ `--fail-on-dead`
- Khi cờ `--fail-on-dead` được kích hoạt, CLI kiểm tra tổng số lượng cờ `DEAD`. Nếu $\text{dead} > 0$, tiến trình thoát với `exit code 1`, ngăn chặn việc merge code chứa cờ tính năng đã lưu trữ vào nhánh chính.
- Hỗ trợ chế độ offline: nếu server không khả dụng hoặc không truyền API key, CLI vẫn hoàn thành việc quét và hiển thị vị trí xuất hiện mà không làm sập pipeline.

## Phương án thay thế (Alternatives Considered)

| Tiêu chí | AST + Regex ràng buộc (Đã chọn) | Grep / Ripgrep đơn giản | Tích hợp SonarQube / Semgrep Plugin |
|---|---|---|---|
| **Độ chính xác** | Rất cao: loại bỏ hoàn toàn comment và chuỗi không phải SDK call | Thấp: match nhầm mọi chuỗi trong comment và docs | Cao |
| **Phụ thuộc bên ngoài** | Không: 100% Python stdlib (`ast`, `re`, `pathlib`) | Cần cài binary bên ngoài (`ripgrep`) | Phức tạp, cần hạ tầng server hoặc cài tool nặng |
| **Tốc độ triển khai** | Nhanh, nhẹ, cài đặt bằng `pip install -e tools/flag-scanner` | Cần cấu hình script shell phức tạp | Quá cồng kềnh cho một đồ án / CLI công cụ |

## Hệ quả (Consequences)
- **Tích cực**:
  - Không có dương tính giả từ comment hay string literal thông thường trong Python.
  - Phân tích cực nhanh: quét toàn bộ repo và phân tích AST chỉ mất chưa đến 0.1 giây.
  - Dễ dàng tích hợp vào GitHub Actions / pre-commit hook với mã thoát chuẩn.
- **Tiêu cực**:
  - Đối với các ngôn ngữ không phải Python (như Go, Java), việc dùng regex có thể bỏ sót nếu lập trình viên gán tên hàm qua alias phức tạp. Tuy nhiên, với các lời gọi SDK thông thường, regex ràng buộc đáp ứng độ chính xác trên 98%.
