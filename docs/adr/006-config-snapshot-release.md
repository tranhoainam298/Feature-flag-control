# ADR-006: Kiến trúc Config Center, Immutable Snapshot Releases, Rollback và Bảo mật Secret

## Trạng thái
Accepted

## Ngày
2026-09-17

## Ngữ cảnh (Context)
Bên cạnh Feature Flags (điều khiển luồng thực thi và phân nhánh logic), hệ thống FlagOps cần một trung tâm cấu hình ứng dụng tập trung (Config Center) — vế thứ hai quan trọng trong đề tài.

Một hệ thống quản lý cấu hình phân tán trong môi trường production đòi hỏi:
1. **Cô lập thay đổi (Draft Isolation)**: Nhà phát triển có thể chỉnh sửa cấu hình dạng bản nháp (draft) mà không ảnh hưởng trực tiếp đến các client đang chạy ở runtime.
2. **Bản phát hành bất biến (Immutable Releases)**: Mọi lần áp dụng cấu hình (publish) phải lưu trữ một snapshot toàn vẹn của tất cả key-value và metadata tại thời điểm đó, có số version tăng tuần tự (1, 2, 3...) và không được phép sửa hay xóa.
3. **Diff Engine minh bạch**: Cho phép người dùng so sánh trực quan giữa bản nháp hiện tại và bản release đang chạy, hoặc giữa 2 release bất kỳ, phân loại chính xác 4 trường hợp: `added`, `removed`, `changed`, `unchanged`.
4. **Cơ chế Rollback an toàn**: Khi xảy ra sự cố, việc rollback về một phiên bản trước đó (ví dụ v1) không được xóa hay sửa các phiên bản trung gian (v2, v3), mà phải tạo ra một release hoàn toàn mới (v4) với nội dung sao chép từ v1 và đánh dấu `is_rollback_of = v1`.
5. **Bảo mật bí mật cấu hình (Secret Management)**: Các biến cấu hình nhạy cảm (`is_secret=true`) phải được mã hóa ở tầng lưu trữ (DB và Snapshot), mặc định trả về chuỗi ẩn `••••••` trên API; chỉ cấp quyền giải mã (reveal) cho vai trò từ `ADMIN` trở lên khi có tham số tường minh `?reveal=true` và phải ghi nhận audit log.
6. **Kiểm tra tính hợp lệ trước khi Release (JSON Schema Validation)**: Mọi config item nếu có schema định nghĩa phải được kiểm tra trước khi tạo release; nếu vi phạm thì từ chối phát hành (mã lỗi 400 `CONFIG_VALIDATION_FAILED`) để ngăn ngừa cấu hình sai lọt vào hệ thống production.

## Quyết định (Decision)

Chúng tôi thiết kế và hiện thực Config Center với các quyết định kỹ thuật sau:

### 1. Mô hình Dữ liệu và Tách biệt Draft - Release
- **`config_namespace`**: Thuộc về một `environment_id`, định danh không gian cấu hình (JSON, YAML, PROPERTIES). Lưu trữ con trỏ `current_release_id` trỏ tới bản phát hành đang kích hoạt.
- **`config_item`**: Lưu trữ các key-value trong bản nháp (draft) của namespace. Các thao tác `GET/PUT /api/v1/namespaces/{n}/items` chỉ đọc và ghi trên bảng này, hoàn toàn không làm thay đổi `current_release_id` hay dữ liệu client đang đọc.
- **`config_release`**: Thực thể **bất biến**. Khi người dùng gọi `POST /api/v1/namespaces/{n}/releases`, hệ thống:
  1. Kiểm tra JSON Schema cho từng item trong draft.
  2. Tính version mới = `MAX(version) + 1`.
  3. Đóng gói snapshot dạng JSONB gồm: `{"configs": {k: v}, "items": [...], "secrets": [...]}`.
  4. Tạo bản ghi `config_release`.
  5. Cập nhật `namespace.current_release_id = release.id`.
  6. Kích hoạt `bump_ruleset_version(env_id)` để xóa cache Redis và phát tin Pub/Sub cho các client/SDK.

### 2. Thuật toán Diff Engine thuần (Pure Python)
- Đặt tại `app/services/config_diff.py`: `calculate_config_diff(old: dict, new: dict) -> dict`.
- Hoàn toàn không phụ thuộc I/O hay database, kiểm thử đạt **100% test coverage**.
- Phân loại rõ ràng 4 trạng thái:
  - `added`: Các key chỉ có trong `new`.
  - `removed`: Các key chỉ có trong `old`.
  - `changed`: Các key có giá trị khác nhau giữa `old` và `new` (cấu trúc `{"old": val_old, "new": val_new}`).
  - `unchanged`: Các key giữ nguyên giá trị.
- Đối với items `is_secret=true`, khi tính diff giữa draft và release cho người dùng thông thường, giá trị được giữ ở dạng mặt nạ `••••••` để chống lộ lọt thông tin.

### 3. Nguyên tắc Bất biến khi Rollback
- Khi gọi `POST /api/v1/namespaces/{n}/releases/{target_version}/rollback`:
  - Tìm bản release có version `target_version`.
  - Tạo một release mới với version kế tiếp (`max_ver + 1`), copy nguyên vẹn `snapshot` của `target_version`, đặt `is_rollback_of = target_release.id`.
  - Cập nhật `namespace.current_release_id` trỏ tới release mới này.
  - Phục hồi lại các item trong bản nháp `config_item` để đồng bộ với snapshot vừa rollback.
  - Tuyệt đối không cập nhật hay xóa bất kỳ release nào đã tồn tại trong lịch sử.

### 4. Mã hóa AES-256-GCM cho Secret
- Đặt tại `app/core/crypto.py`:
  - Thuật toán `AESGCM` từ thư viện chuẩn bảo mật `cryptography`.
  - Khóa chính được dẫn xuất an toàn bằng SHA-256 từ biến môi trường `CONFIG_MASTER_KEY` thành khóa 32 bytes (256-bit).
  - Khởi tạo `nonce` 12 bytes ngẫu nhiên (`os.urandom(12)`) cho mỗi lần mã hóa, ghép vào đầu ciphertext trước khi mã hóa Base64: `base64(nonce + ciphertext + tag)`.
  - Cơ sở dữ liệu và snapshot chỉ lưu trữ chuỗi Base64 ciphertext này.
  - Phân quyền reveal: Chỉ tài khoản có vai trò `ADMIN` hoặc `OWNER` trong organization mới có quyền gửi query param `?reveal=true`. Mỗi lần reveal tạo một bản ghi `audit_log` với action `config.secret_revealed`.
  - SDK / Hot path: Endpoint `GET /eval/v1/config/{namespace}` tự động giải mã secret nếu API key có scope `SERVER`; nếu scope `CLIENT` thì trả về mặt nạ `••••••`.

### 5. Kiểm định JSON Schema
- Thư viện `jsonschema` chuẩn CNCF / Draft-07/2020-12.
- Trước khi thực hiện release, hàm `validate_item_schema` chuyển đổi kiểu dữ liệu tương ứng của item (`INT`, `FLOAT`, `BOOL`, `JSON`, `STRING`) rồi đối chiếu với `json_schema`.
- Nếu có bất kỳ item nào không thỏa mãn, hệ thống ném ngoại lệ `FlagOpsError(code="CONFIG_VALIDATION_FAILED", status_code=400, details={"errors": [...]})` và hủy bỏ toàn bộ giao dịch, đảm bảo không có release hỏng nào được sinh ra.

## Đánh giá & Hệ quả

### Ưu điểm
- **An toàn tuyệt đối**: Môi trường production không bao giờ bị ảnh hưởng bởi những chỉnh sửa dở dang trong quá trình soạn thảo cấu hình.
- **Dễ dàng kiểm tra và truy vết**: Mọi thay đổi đều được so sánh (diff) trước khi phát hành, lịch sử phát hành được lưu trữ vĩnh viễn và cho phép rollback tức thời chỉ bằng một lời gọi API.
- **Bảo mật đa tầng**: Secret được mã hóa tại chỗ (at-rest), che giấu khi truyền qua API thông thường, và chỉ giải mã khi có quyền quản trị hoặc phục vụ cho ứng dụng backend (SERVER key).
- **Phù hợp triết lý tối giản (`ponytail`)**: Tận dụng triệt để JSONB của PostgreSQL để lưu snapshot, không cần bảng phụ phức tạp, code diff engine viết bằng Python stdlib thuần túy.
