# Progress Report — Slice 7: Evaluation API (Hot Path)

**Ngày hoàn thành:** 2026-09-16  
**Trạng thái:** HOÀN THÀNH (100% tiêu chí Definition of Done)  
**Kỹ năng áp dụng:** `api-contract-rest`, `python-fastapi-backend`, `security-hardening`, `ponytail`

---

## 1. Mục tiêu Slice 7

Tách riêng đường API đánh giá (hot path) khỏi đường quản trị, phục vụ SDK/client với lưu lượng cao, xác thực bằng API key thay vì JWT.

Router đặt tại `app/api/eval/` (tách khỏi admin), prefix `/eval/v1`:

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/eval/v1/flags/{flag_key}/evaluate` | Đánh giá một flag |
| POST | `/eval/v1/flags/evaluate-all` | Đánh giá tất cả flag của environment |
| GET  | `/eval/v1/ruleset` | Tải ruleset (ETag / 304) |
| POST | `/eval/v1/events` | Nhận batch evaluation event (ghi bất đồng bộ) |
| GET  | `/eval/v1/stream` | SSE stream thông báo thay đổi ruleset (heartbeat 25s) |

---

## 2. Xác thực — Header `X-FlagOps-Key` (KHÔNG dùng JWT)

Luồng: raw key → `SHA-256` → tra `api_key.key_hash` → gắn `environment`.

| Trường hợp | Kết quả |
|---|---|
| Key không tồn tại | `401 UNAUTHORIZED` |
| Key đã revoke (`revoked_at IS NOT NULL`) | `401 UNAUTHORIZED` |
| Key hết hạn (`expires_at < now`) | `401 UNAUTHORIZED` |
| Key scope `CLIENT` | Chỉ trả flag có `is_client_visible = true` |
| Key env A gọi ruleset env B | `403 FORBIDDEN` |

Dependency `verify_api_key` (`app/core/deps.py:49`) hash key bằng SHA-256 rồi tra DB, `selectinload(ApiKey.environment)`. Không log raw key.

---

## 3. Chống N+1 — Ruleset nạp bằng MỘT truy vấn gộp

`load_ruleset_bundle()` (`app/services/eval.py:100`) nạp toàn bộ ruleset bằng **4 truy vấn cố định**, không phụ thuộc số flag:

1. `Flag` + `joinedload(variations)`
2. `FlagEnvironmentSetting` + `joinedload(targeting_rules)`
3. `IndividualOverride` (join setting theo `environment_id`)
4. `Segment` (theo `project_id`)

Test N+1 dùng `QueryCounter` (hook `before_cursor_execute`) — 50 flag + 50 rule + 50 override yêu cầu `queries < 5`. Kết quả thực tế: **4 query**.

---

## 4. ETag / 304 Not Modified

- `ETag` = `environment.ruleset_version` (BIGINT, tăng mỗi khi có thay đổi flag/setting).
- Client gửi `If-None-Match: "142"`; nếu version chưa đổi → `304` body rỗng.
- **304 phải nhanh:** chỉ đọc `environment.ruleset_version` (`get_environment_version`, 1 query scalar), KHÔNG nạp toàn bộ ruleset.
- Version đổi → `200` + body ruleset mới + header `ETag` mới.

---

## 5. Ghi nhận (tracking & events)

- **`last_evaluated_at`**: `EvaluationTracker` gom `setting_id` vào set, flush theo batch (mặc định 50) bằng **một** `UPDATE ... WHERE id IN (...)`, tránh UPDATE mỗi request.
- **`POST /eval/v1/events`**: hash `context_key` bằng SHA-256 trước khi lưu vào `evaluation_event.context_key_hash`. KHÔNG lưu `userId` gốc (bảo vệ dữ liệu cá nhân). Response `202 Accepted`.

---

## 6. Kết quả kiểm thử Definition of Done

### A. Test eval theo yêu cầu:
```bash
$ docker compose exec -T api pytest app/tests/ -k eval -v
```
**Kết quả: 22 passed, 164 deselected.**

Các ca bao phủ đúng yêu cầu:
- `test_evaluate_single_flag_returns_correct_value_variant_reason` — value/variant/reason đúng.
- `test_evaluate_all_returns_all_environment_flags` — trả đủ flag của environment.
- `test_ruleset_etag_header_and_304_not_modified` — lần 1 `200 + ETag`, lần 2 `If-None-Match` → `304` body rỗng.
- `test_flag_change_bumps_version_and_invalidates_etag` — sửa flag → version tăng → ETag đổi → `200` lại.
- `test_client_key_does_not_see_private_flag` — CLIENT key không thấy flag private (ruleset + evaluate trả `404`).
- `test_dev_key_accessing_prod_ruleset_returns_403` — key env dev gọi ruleset prod → `403`.
- `test_revoked_or_invalid_api_key_returns_401` — key revoke `401`, key không tồn tại `401`, thiếu header `401`.
- `test_n_plus_one_ruleset_50_flags_under_5_queries` — 50 flag `< 5` query.
- `test_post_evaluation_events_hashes_context_key_and_persists` — SHA-256 hash, không lưu raw userId.
- `test_evaluation_tracker_batches_last_evaluated_at` — tracker gom batch, chưa UPDATE tới khi flush.
- `test_stream_emits_ruleset_updated_event` — SSE stream phát `ruleset_updated` ngay lập tức.

### B. Toàn bộ Test Suite:
```bash
$ docker compose exec -T api pytest
```
**Kết quả: 186 passed** — không phá slice trước.

### C. Lint & Type check:
```bash
$ docker compose exec -T api ruff check .
$ docker compose exec -T api mypy app
```
**Kết quả:** `All checks passed!` và `Success: no issues found in 70 source files`.

---

## 7. Thực thi Live CURL (Definition of Done)

### 1) GET ruleset lần đầu → `200` + `ETag`
```bash
$ curl -s -i -H 'X-FlagOps-Key: fo_srv_...' localhost:8000/eval/v1/ruleset
```
```
HTTP/1.1 200 OK
etag: "0"
content-type: application/json

{"rulesetVersion":0,"flags":{},"segments":{}}
```

### 2) GET ruleset kèm `If-None-Match` → `304` (body rỗng)
```bash
$ curl -s -i -H 'X-FlagOps-Key: fo_srv_...' -H 'If-None-Match: "0"' localhost:8000/eval/v1/ruleset
```
```
HTTP/1.1 304 Not Modified
etag: "0"
```

---

### 3) SSE stream → `ruleset_updated` + heartbeat
```bash
$ curl -s -N -H 'X-FlagOps-Key: fo_srv_...' localhost:8000/eval/v1/stream
```
```
event: ruleset_updated
data: {"environmentId":"...","rulesetVersion":0}

event: heartbeat
data: {}
```

---

## 8. Ghi chú ponytail

- 304 fast-path đọc đúng 1 scalar `ruleset_version`, không dựng bundle — đúng yêu cầu "304 phải nhanh".
- Ruleset cố định 4 query (không phải 1 query khổng lồ với 4 lần join chồng chéo) — đủ để < 5, dễ đọc, tránh cartesian explosion khi join rules × overrides × segments.
- `EvaluationTracker` là singleton in-process; đủ cho batch giảm UPDATE. Nếu chạy multi-worker cần flush định kỳ/Redis — ghi nhận khi scale.
- SSE stream dùng **polling DB** (`ruleset_version` mỗi 2s) thay vì Redis pub/sub — 0 phụ thuộc write-path, đúng trên multi-worker, đủ cho mục đích demo. Redis cache invalidation để sau khi cần.