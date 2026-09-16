# Progress Report — Slice 6: Segment & Targeting Rule

**Ngày hoàn thành:** 2026-09-16  
**Trạng thái:** HOÀN THÀNH (100% tiêu chí Definition of Done)  
**Kỹ năng áp dụng:** `python-fastapi-backend`, `api-contract-rest`, `python-testing-pytest`, `ponytail`

---

## 1. Mục tiêu Slice 6

Kết nối tầng API & Database với Evaluation Engine thuần khiết (Pure Engine) đã xây dựng ở Slice 5:
1. **Quản lý Segment (Nhóm đối tượng)**:
   - `GET /api/v1/projects/{project_id}/segments`: Danh sách segment theo project.
   - `POST /api/v1/projects/{project_id}/segments`: Tạo segment mới kèm cây điều kiện `conditions`. Chống trùng key trong cùng project (409 `SEGMENT_KEY_EXISTS`).
   - `GET /api/v1/projects/{project_id}/segments/{segment_id}`: Lấy chi tiết segment.
   - `PATCH /api/v1/projects/{project_id}/segments/{segment_id}`: Cập nhật tên, mô tả, điều kiện.
   - `DELETE /api/v1/projects/{project_id}/segments/{segment_id}`: Xóa segment.

2. **Quản lý Targeting Rules (Quy tắc nhắm mục tiêu)**:
   - `GET /api/v1/flags/{flag_id}/environments/{env_id}/rules`: Lấy toàn bộ rule sắp xếp theo priority.
   - `PUT /api/v1/flags/{flag_id}/environments/{env_id}/rules`: Ghi đè toàn bộ tập rule một cách **Atomic** trong một Database Transaction duy nhất. Xóa sạch rule cũ và tạo rule mới. Nếu lỗi giữa chừng $\to$ Rollback toàn bộ trạng thái DB. Tự động tăng `ruleset_version` và ghi nhận `AuditLog`.

3. **Quản lý Individual Overrides (Ghi đè cá nhân)**:
   - `POST /api/v1/flags/{flag_id}/environments/{env_id}/overrides`: Tạo hoặc cập nhật override cho context key cụ thể.
   - `DELETE /api/v1/flags/{flag_id}/environments/{env_id}/overrides/{override_id}`: Xóa override.

4. **Endpoint Mô phỏng Đánh giá Cờ tính năng (Simulate)**:
   - `POST /api/v1/flags/{flag_id}/environments/{env_id}/simulate`: Nạp ruleset từ DB, khởi tạo `EvaluationContext`, gọi `engine.evaluate()` và trả về:
     - `value`, `variant`, `reason`
     - `matched_rule_id`, `matched_rule_description`
     - `trace`: Mảng từng rule được duyệt tuần tự, trạng thái khớp/không khớp và lý do, cực kỳ trực quan khi demo và gỡ lỗi.

---

## 2. Quy tắc Validation chặt chẽ khi ghi Rule

| Quy tắc kiểm tra | Mã HTTP | Mã lỗi Error Envelope | Hành vi xử lý |
|---|---|---|---|
| **Priority trùng lặp** | `422 Unprocessable` | `DUPLICATE_PRIORITY` | Chặn đứng nếu danh sách rule có 2 rule cùng priority |
| **Tổng weight distribution $\neq 100$** | `422 Unprocessable` | `INVALID_DISTRIBUTION_WEIGHT` | Tổng trọng số phân phối bắt buộc phải chính xác 100% |
| **Variation không thuộc Flag** | `422 Unprocessable` | `INVALID_VARIATION` | Không cho phép dùng variation_id của flag khác |
| **Toán tử không hợp lệ** | `422 Unprocessable` | `INVALID_OPERATOR` | Toán tử phải thuộc danh sách 22 toán tử hoặc `IS_ONE_OF_SEGMENT` |
| **Độ sâu cây điều kiện $> 5$** | `400 Bad Request` | `CONDITION_DEPTH_EXCEEDED` | Giới hạn đệ quy tối đa 5 tầng lồng nhau |
| **Segment thuộc project khác** | `422 Unprocessable` | `SEGMENT_PROJECT_MISMATCH` | Tham chiếu qua `segment_id` hoặc `IS_ONE_OF_SEGMENT` phải cùng project |
| **Atomic Transaction** | Rollback | — | Bất kỳ lỗi nào trong quá trình validate hoặc commit đều rollback, giữ nguyên tập rule cũ |

---

## 3. Kết quả kiểm thử Definition of Done

### A. Chạy test targeting theo yêu cầu:
```bash
$ docker compose exec -T api pytest app/tests/ -k "segment or rule or simulate" -v
```
**Kết quả:**
- **20 passed, 155 deselected** (100% passed).

### B. Chạy toàn bộ Test Suite của hệ thống:
```bash
$ docker compose exec -T api pytest -v
```
**Kết quả:**
- **175 passed** (toàn bộ test từ S00 đến S06 đều xanh tuyệt đối).

### C. Kiểm tra Linting & Type Check:
```bash
$ docker compose exec -T api ruff check app scripts
$ docker compose exec -T api mypy app scripts
```
**Kết quả:**
- `All checks passed!`
- `Success: no issues found in 66 source files`.

---

## 4. Thực thi Live CURL Endpoint `/simulate` kèm Trace

Đã kích hoạt và gọi thực tế qua HTTP vào container `flagops-api` (`http://localhost:8000`):

### Kịch bản Demo:
- Flag: `checkout_v2` (BOOLEAN, default: `false` / `off`).
- Segment: `beta_testers` (`email ENDS_WITH "@flagops.dev"`).
- Rule 1 (Priority 1): `IS_ONE_OF_SEGMENT` $\to$ `beta_testers` $\to$ Trả về `true` / `on` (100%).
- Individual Override: `vip_ceo` $\to$ Trả về `true` / `on`.

---

### Context 1: Individual Override (`targetingKey: "vip_ceo"`)
```bash
$ curl -s -X POST http://localhost:8000/api/v1/flags/925a4b9e-b980-44a9-b0ae-76d3db8f9ed7/environments/a61aa42d-ad0a-4a3f-9b42-5e077d60206b/simulate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"context": {"targetingKey": "vip_ceo", "email": "ceo@external.com"}}'
```
**Kết quả trả về:**
```json
{
  "flag_key": "checkout_v2_7c4e",
  "value": true,
  "variant": "on",
  "reason": "TARGETING_MATCH",
  "matched_rule_id": null,
  "matched_rule_description": null,
  "trace": [
    {
      "rule_id": null,
      "priority": null,
      "description": "Individual override matched for 'vip_ceo'",
      "matched": true,
      "reason": "OVERRIDE_MATCH"
    }
  ]
}
```

---

### Context 2: Targeting Rule Match (`email: "engineer@flagops.dev"`)
```bash
$ curl -s -X POST http://localhost:8000/api/v1/flags/925a4b9e-b980-44a9-b0ae-76d3db8f9ed7/environments/a61aa42d-ad0a-4a3f-9b42-5e077d60206b/simulate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"context": {"targetingKey": "alice", "email": "engineer@flagops.dev"}}'
```
**Kết quả trả về:**
```json
{
  "flag_key": "checkout_v2_7c4e",
  "value": true,
  "variant": "on",
  "reason": "TARGETING_MATCH",
  "matched_rule_id": "c7aef39a-cce4-4a83-a324-511c380cedff",
  "matched_rule_description": "Beta Testers Segment receives New Checkout",
  "trace": [
    {
      "rule_id": "c7aef39a-cce4-4a83-a324-511c380cedff",
      "priority": 1,
      "description": "Beta Testers Segment receives New Checkout",
      "matched": true,
      "reason": "Conditions matched"
    }
  ]
}
```

---

### Context 3: Default Fallback (`email: "visitor@gmail.com"`)
```bash
$ curl -s -X POST http://localhost:8000/api/v1/flags/925a4b9e-b980-44a9-b0ae-76d3db8f9ed7/environments/a61aa42d-ad0a-4a3f-9b42-5e077d60206b/simulate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"context": {"targetingKey": "bob", "email": "visitor@gmail.com"}}'
```
**Kết quả trả về:**
```json
{
  "flag_key": "checkout_v2_7c4e",
  "value": false,
  "variant": "off",
  "reason": "DEFAULT",
  "matched_rule_id": null,
  "matched_rule_description": null,
  "trace": [
    {
      "rule_id": "c7aef39a-cce4-4a83-a324-511c380cedff",
      "priority": 1,
      "description": "Beta Testers Segment receives New Checkout",
      "matched": false,
      "reason": "Conditions did not match"
    },
    {
      "rule_id": null,
      "priority": null,
      "description": "No rules matched, fell back to default variation",
      "matched": false,
      "reason": "DEFAULT_FALLBACK"
    }
  ]
}
```
