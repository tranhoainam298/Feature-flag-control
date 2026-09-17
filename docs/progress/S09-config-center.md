# Progress Report — Slice 9: Config Center

**Ngày hoàn thành:** 2026-09-17  
**Trạng thái:** HOÀN THÀNH (100% tiêu chí Definition of Done)  
**Kỹ năng áp dụng:** `python-fastapi-backend`, `postgres-alembic-migrations`, `api-contract-rest`, `security-hardening`, `ponytail`, `tdd`

---

## 1. Mục tiêu Slice 9

Hiện thực vế thứ hai quan trọng của đề tài FlagOps: **Trung tâm Cấu hình Ứng dụng (Config Center)**. Hệ thống cho phép quản lý cấu hình theo namespace, biên soạn bản nháp (draft) độc lập, so sánh diff, phát hành snapshot bất biến (immutable releases), rollback an toàn, mã hóa secret AES-256-GCM và kiểm định JSON Schema trước khi release.

Danh sách endpoint hoàn thành:

| Method | Endpoint | Mô tả & Phân quyền |
|---|---|---|
| `GET` | `/api/v1/environments/{e}/namespaces` | Danh sách namespace theo môi trường (VIEWER+) |
| `POST` | `/api/v1/environments/{e}/namespaces` | Tạo namespace mới (DEVELOPER+) |
| `GET` | `/api/v1/namespaces/{n}/items` | Lấy danh sách item bản nháp hiện tại (VIEWER+, `?reveal=true` yêu cầu ADMIN+) |
| `PUT` | `/api/v1/namespaces/{n}/items` | Cập nhật bản nháp (DEVELOPER+) |
| `GET` | `/api/v1/namespaces/{n}/pending-diff` | Diff giữa bản nháp và release đang chạy (VIEWER+) |
| `POST` | `/api/v1/namespaces/{n}/releases` | Publish release mới từ draft (DEVELOPER+) |
| `GET` | `/api/v1/namespaces/{n}/releases` | Lịch sử releases giảm dần theo version (VIEWER+) |
| `GET` | `/api/v1/namespaces/{n}/releases/{v1}/diff/{v2}` | Diff giữa 2 phiên bản release bất kỳ (VIEWER+) |
| `POST` | `/api/v1/namespaces/{n}/releases/{v}/rollback` | Rollback về version v (tạo release mới, giữ nguyên lịch sử) (DEVELOPER+) |
| `GET` | `/eval/v1/config/{namespace}` | Client SDK đọc cấu hình (X-FlagOps-Key + ETag/304) |

---

## 2. Các nguyên tắc cốt lõi đã thực hiện

### 2.1. Draft Isolation & Snapshot Bất biến
- Sửa `config_item` qua `PUT /items` chỉ cập nhật bản nháp, con trỏ `namespace.current_release_id` không đổi.
- Client SDK gọi `GET /eval/v1/config/{namespace}` vẫn đọc dữ liệu từ snapshot của `current_release_id`.
- Khi publish:
  - Kiểm tra toàn bộ JSON Schema.
  - Tăng version tuần tự `max_ver + 1` (1, 2, 3...).
  - Đóng gói toàn bộ cấu hình, kiểu dữ liệu, schema và secret vào `snapshot` JSONB.
  - Cập nhật `namespace.current_release_id`.
  - Tự động gọi `bump_ruleset_version` để xóa cache Redis và bắn tín hiệu Pub/Sub.

### 2.2. Rollback Bất biến (Zero Mutation trên Release cũ)
- Rollback về phiên bản v1 khi đang ở v2, v3 sẽ tạo ra release **v4** với `is_rollback_of = v1.id`.
- Snapshot của v4 sao chép nguyên trạng từ v1.
- Tuyệt đối không xóa hay sửa các bản ghi v1, v2, v3 trong database.
- Tự động phục hồi lại bản nháp `config_item` theo đúng trạng thái của v1.

### 2.3. Pure Diff Engine (`app/services/config_diff.py`)
- Viết bằng Python thuần, không phụ thuộc database hay network.
- `calculate_config_diff(old, new) -> dict` trả về chính xác 4 nhóm:
  - `added`: các key xuất hiện mới
  - `removed`: các key bị xóa
  - `changed`: các key bị đổi giá trị (`{"old": ..., "new": ...}`)
  - `unchanged`: các key giữ nguyên
- Hỗ trợ dữ liệu lồng nhau, kiểu số, chuỗi, boolean, None, và dictionary rỗng.
- **Coverage đạt 100%** (9 unit tests).

### 2.4. Mã hóa Secret (`app/core/crypto.py`)
- Thuật toán chuẩn bảo mật: `AES-256-GCM` từ thư viện `cryptography`.
- Khóa 32 bytes dẫn xuất từ `CONFIG_MASTER_KEY` qua `SHA-256`.
- `nonce` 12 bytes ngẫu nhiên cho mỗi lần mã hóa, lưu trữ `base64(nonce + ciphertext + tag)`.
- Giá trị lưu trong bảng `config_item.value` và `config_release.snapshot` hoàn toàn là ciphertext mã hóa.
- API mặc định trả về `"••••••"`.
- Chỉ người dùng có role >= `ADMIN` và query param `?reveal=true` mới nhận được plaintext; mỗi lần reveal ghi nhận một bản ghi `audit_log` với action `"config.secret_revealed"`.
- `GET /eval/v1/config/{namespace}`: tự động giải mã plaintext cho API key có scope `SERVER`, và trả về `"••••••"` cho API key có scope `CLIENT`.

### 2.5. Kiểm định JSON Schema
- Thư viện `jsonschema` chuẩn.
- Ép kiểu dữ liệu (`INT`, `FLOAT`, `BOOL`, `JSON`, `STRING`) trước khi validate với schema.
- Nếu có lỗi, API trả về `400 Bad Request` với mã `CONFIG_VALIDATION_FAILED` và chi tiết lỗi từng key.
- Giao dịch bị hủy bỏ, **không có release nào được tạo ra**.

---

## 3. Kết quả Kiểm thử (Test Results)

### 3.1. Test Suite Config
```bash
$ docker compose exec -T api pytest app/tests/ -k config -v
=================== 16 passed, 196 deselected in 12.69s ===================
```
Bao gồm:
- `test_draft_changes_invisible_to_client_until_publish`: PASSED
- `test_version_increments_1_2_3`: PASSED
- `test_diff_four_cases`: PASSED
- `test_rollback_creates_new_release_and_preserves_history`: PASSED
- `test_secret_encryption_and_reveal_permissions`: PASSED
- `test_schema_validation_prevents_release_on_failure`: PASSED
- `test_developer_publish_and_etag_304`: PASSED
- 9 unit tests cho Diff Engine: PASSED

### 3.2. Coverage Diff Engine & Crypto
```bash
$ docker compose exec -T api pytest app/tests/unit/test_config_diff.py --cov=app.services.config_diff
Name                          Stmts   Miss  Cover
-------------------------------------------------
app/services/config_diff.py      16      0   100%

$ docker compose exec -T api pytest app/tests/unit/test_crypto.py --cov=app.core.crypto
Name                 Stmts   Miss  Cover
-------------------------------------------------
app/core/crypto.py      23      1    96%
```

### 3.3. Toàn bộ hệ thống (Toàn bộ 212 tests)
```bash
$ docker compose exec -T api pytest
======================= 212 passed in 56.56s =======================
```

### 3.4. Lint & Static Analysis
```bash
$ docker compose exec -T api ruff check .
All checks passed!

$ docker compose exec -T api mypy app
Success: no issues found in 80 source files
```

---

## 4. Minh chứng Live Curl Demo (Sửa → Diff → Publish → Rollback)

Trích xuất trực tiếp từ phiên chạy thực tế qua curl:

### Bước 1: Soạn bản nháp (PUT /items)
```bash
$ curl.exe -s -X PUT http://localhost:8000/api/v1/namespaces/b4f6903d/items \
  -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"items": [
    {"key": "database.url", "value": "postgresql://pg:5432/billing", "value_type": "STRING"},
    {"key": "max_connections", "value": "20", "value_type": "INT"},
    {"key": "api.secret", "value": "very-secret-token-xyz", "value_type": "STRING", "is_secret": true}
  ]}'
```

### Bước 2: Xem Diff trước khi Release (GET /pending-diff)
```json
{
  "added": {
    "api.secret": "••••••",
    "database.url": "postgresql://pg:5432/billing",
    "max_connections": "20"
  },
  "removed": {},
  "changed": {},
  "unchanged": {}
}
```

### Bước 3: Publish Release v1 & Client đọc
```bash
$ curl.exe -s -X POST http://localhost:8000/api/v1/namespaces/b4f6903d/releases \
  -H "Authorization: Bearer <TOKEN>" -d '{"comment": "Initial release of billing configs"}'

$ curl.exe -s -H "X-FlagOps-Key: <SERVER_API_KEY>" http://localhost:8000/eval/v1/config/billing-service
{
  "version": 1,
  "namespace": "billing-service",
  "configs": {
    "api.secret": "very-secret-token-xyz",
    "database.url": "postgresql://pg:5432/billing",
    "max_connections": "20"
  }
}
```

### Bước 4: Chỉnh sửa bản nháp lần 2 (Đủ 4 trường hợp Diff)
```bash
# Thêm stripe.mode, xóa database.url, sửa max_connections từ 20 thành 50, giữ nguyên secret
$ curl.exe -s -H "Authorization: Bearer <TOKEN>" http://localhost:8000/api/v1/namespaces/b4f6903d/pending-diff
{
  "added": {
    "stripe.mode": "live"
  },
  "removed": {
    "database.url": "postgresql://pg:5432/billing"
  },
  "changed": {
    "max_connections": {
      "old": "20",
      "new": "50"
    }
  },
  "unchanged": {
    "api.secret": "••••••"
  }
}
```

### Bước 5: Publish Release v2 & Rollback về v1
```bash
# Publish v2
$ curl.exe -s -X POST http://localhost:8000/api/v1/namespaces/b4f6903d/releases ...
# Release v2 version: 2

# Thực hiện Rollback về v1
$ curl.exe -s -X POST http://localhost:8000/api/v1/namespaces/b4f6903d/releases/1/rollback \
  -H "Authorization: Bearer <TOKEN>" -d '{"comment": "Emergency rollback to v1"}'
{
  "id": "3ce9129d-713e-4f65-a4c1-2fe828d8857e",
  "namespace_id": "b4f6903d-534e-4407-833f-31b9318bd3f4",
  "version": 3,
  "comment": "Rollback to v1",
  "is_rollback_of": "b467f127-746e-47b9-b95d-fa3a4cd6188a"
}
```

### Bước 6: Kiểm tra Client sau Rollback
```bash
$ curl.exe -s -H "X-FlagOps-Key: <SERVER_API_KEY>" http://localhost:8000/eval/v1/config/billing-service
{
  "version": 3,
  "namespace": "billing-service",
  "configs": {
    "api.secret": "very-secret-token-xyz",
    "database.url": "postgresql://pg:5432/billing",
    "max_connections": "20"
  }
}
```
*Lịch sử release được bảo toàn nguyên vẹn gồm cả 3 bản ghi (v3, v2, v1).*
