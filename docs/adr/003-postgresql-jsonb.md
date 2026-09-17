# ADR-003: Lưu trữ Cây Điều kiện và Biến thể bằng PostgreSQL JSONB

## Trạng thái
Accepted

## Ngày
2026-09-16

## Ngữ cảnh (Context)
Hệ thống Feature Flag và Remote Configuration đòi hỏi khả năng biểu diễn các cấu trúc dữ liệu rất linh hoạt:
1. **Cây điều kiện nhắm mục tiêu (Targeting Rule Conditions & Segments)**:
   - Các điều kiện có thể lồng ghép logic `AND` / `OR` nhiều tầng, với các toán tử đa dạng (`==`, `IN`, `CONTAINS`, `MATCHES_REGEX`, `SEMVER_GT`).
   - Số lượng thuộc tính người dùng truyền vào ngữ cảnh (`country`, `plan`, `appVersion`, `device.os`, v.v.) không cố định và không thể đoán trước trước khi triển khai.
2. **Giá trị biến thể (Variations & Config Snapshots)**:
   - Flag và Config hỗ trợ cả 4 kiểu dữ liệu: `BOOLEAN`, `STRING`, `NUMBER`, và `JSON` (object/array phức tạp).
   - Bản phát hành cấu hình (`config_release`) cần đóng băng toàn bộ trạng thái của một namespace tại thời điểm publish để phục vụ diff và rollback.

Nếu sử dụng mô hình Cơ sở dữ liệu Quan hệ truyền thống (RDBMS Normalization) với các bảng quan hệ riêng lẻ hoặc mô hình Entity-Attribute-Value (EAV):
- Việc truy vấn một cờ có hàng chục điều kiện và quy tắc đòi hỏi phải JOIN qua 6–8 bảng quan hệ khác nhau (`flags` → `flag_settings` → `targeting_rules` → `rule_conditions` → `condition_values`...).
- Gây nghẽn truy vấn (Query Bottleneck), độ phức tạp mã nguồn ORM tăng vọt và rất khó xây dựng bản snapshot bất biến khi publish/rollback.
- Mặt khác, nếu dùng hoàn toàn cơ sở dữ liệu NoSQL (MongoDB, DynamoDB), hệ thống sẽ mất đi tính toàn vẹn tham chiếu (Foreign Key Integrity) và giao dịch ACID giữa người dùng, tổ chức, quyền RBAC và audit log.

## Quyết định (Decision)
Chúng tôi quyết định sử dụng **PostgreSQL 16** với kiểu dữ liệu nhị phân **JSONB** để lưu trữ cây điều kiện (`conditions`), phân bổ rollout (`distribution`), giá trị biến thể (`variation.value`) và bản chụp cấu hình (`config_release.snapshot`).

### 1. Kiến trúc Lai (Hybrid Relational + JSONB Document)
- **Tầng Cấu trúc Cố định (Relational Skeleton)**: Các thực thể có cấu trúc chặt chẽ như `user`, `organization`, `project`, `environment`, `flag`, `api_key`, `audit_log` được mô hình hóa thành các bảng quan hệ chuẩn với Foreign Key, Unique Index và Cascade Delete.
- **Tầng Tài liệu Linh hoạt (Document Inside Columns)**:
  - Bảng `flag_environment_setting` và `targeting_rule`: lưu trường `conditions` và `distribution` dạng JSONB.
  - Bảng `variation`: lưu trường `value` dạng JSONB, cho phép chứa bất kỳ kiểu dữ liệu hợp lệ nào của JSON.
  - Bảng `config_release`: lưu trường `snapshot` dạng JSONB chứa toàn bộ cặp key-value đóng băng.

### 2. Định dạng Cây Điều kiện JSONB Chuẩn hóa
Cây điều kiện được lưu theo cấu trúc cây AST (Abstract Syntax Tree) chuẩn hóa:
```json
{
  "operator": "AND",
  "conditions": [
    {
      "property": "country",
      "operator": "IN",
      "value": ["VN", "TH", "SG"]
    },
    {
      "operator": "OR",
      "conditions": [
        {"property": "plan", "operator": "==", "value": "premium"},
        {"property": "beta_tester", "operator": "==", "value": true}
      ]
    }
  ]
}
```

### 3. Tối ưu Hiệu năng với JSONB
- Dữ liệu JSONB được PostgreSQL phân tích cú pháp (parsed) sẵn dạng nhị phân, loại bỏ khoảng trắng thừa và hỗ trợ tìm kiếm nhanh.
- Khi tải ruleset cho một môi trường (`GET /eval/v1/ruleset`), API chỉ cần thực hiện 1 truy vấn SQL duy nhất kết hợp `flag_environment_setting` với `targeting_rule`, nạp toàn bộ cấu hình vào bộ nhớ đệm Redis mà không cần hàng chục câu lệnh JOIN phụ trợ.

## Phương án thay thế (Alternatives Considered)

| Phương án | Ưu điểm | Nhược điểm | Lý do không chọn |
|---|---|---|---|
| **Chuẩn hóa RDBMS (Bảng `rule_condition`, `condition_group`)** | Toàn vẹn tham chiếu ở mọi cấp độ, truy vấn SQL quan hệ truyền thống | Phải JOIN 6–8 bảng cho mỗi cờ; không thể biểu diễn linh hoạt cây điều kiện lồng nhau; schema migration cực kỳ phức tạp khi thêm toán tử | Gây nghẽn hiệu năng khi nạp ruleset; độ phức tạp ORM quá lớn |
| **Mô hình Entity-Attribute-Value (EAV)** | Linh hoạt thêm thuộc tính | Mất hoàn toàn kiểm tra kiểu dữ liệu; truy vấn JOIN bảng chính nó (Self-JOIN) nhiều lần; hiệu năng kém nhất trong các mô hình | EAV là anti-pattern nổi tiếng trong thiết kế cơ sở dữ liệu quan hệ |
| **Sử dụng NoSQL Document Database (MongoDB)** | Tự nhiên với dữ liệu dạng JSON, phân tán ngang tốt | Mất ràng buộc khóa ngoại (Foreign Keys) giữa user, org, project; giao dịch đa tài liệu phức tạp; cần duy trì 2 hệ CSDL nếu dùng song song với SQL | Làm tăng chi phí hạ tầng và vận hành; không tận dụng được sức mạnh toàn diện của PostgreSQL |

## Hệ quả (Consequences)

### Tích cực
- **Tốc độ nạp ruleset tối ưu**: Nạp toàn bộ cây điều kiện của một environment chỉ với 1 câu query duy nhất, giảm độ trễ truy vấn từ 25ms xuống dưới 2ms.
- **Tính linh hoạt tối đa**: Bổ sung toán tử mới hoặc mở rộng cấu trúc điều kiện mà không cần chạy Alembic migration để sửa đổi lược đồ bảng.
- **Rollback và Diff nguyên tử**: Snapshot của toàn bộ namespace cấu hình được lưu trọn vẹn trong một trường JSONB, cho phép tính diff và rollback trong 1 câu lệnh UPDATE duy nhất.

### Tiêu cực & Biện pháp giảm thiểu
- **Không có schema enforcement cấp database**: PostgreSQL không tự kiểm tra cấu trúc bên trong JSONB nếu không có CHECK constraint.
  - *Biện pháp*: Toàn bộ payload JSONB được validate chặt chẽ ở tầng API bằng **Pydantic v2 schemas** trước khi ghi xuống CSDL.
- **Nguy cơ tấn công lồng sâu (Deep Nesting)**: Người dùng có thể gửi cây điều kiện lồng 100 tầng gây tràn bộ nhớ.
  - *Biện pháp*: Giới hạn độ sâu tối đa của cây JSONB là 10 tầng (`ConditionDepthExceeded` error code).
