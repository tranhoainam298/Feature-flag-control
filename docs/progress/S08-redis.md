# Progress Report — Slice 8: Redis Cache, Pub/Sub & Fail-Open Rate Limiting

**Ngày hoàn thành:** 2026-09-17  
**Trạng thái:** HOÀN THÀNH (100% tiêu chí Definition of Done)  
**Kỹ năng áp dụng:** `python-fastapi-backend`, `api-contract-rest`, `security-hardening`, `ponytail`

---

## 1. Mục tiêu Slice 8

Triển khai hạ tầng đệm và kiểm soát lưu lượng với Redis cho hot path của FlagOps với 3 công dụng:

| # | Công dụng | Key / Channel | Chi tiết kỹ thuật |
|---|---|---|---|
| 1 | **Cache ruleset** | `ruleset:{environment_id}` | TTL 300s (cấu hình qua `RULESET_CACHE_TTL_SECONDS`), chỉ lưu SERVER scope |
| 2 | **Pub/Sub** | `flagops:ruleset:{environment_id}` | Phát thông báo mang `environment_id` ngay khi cờ hoặc setting đổi |
| 3 | **Rate limit** | `ratelimit:{api_key_id}:{minute}` | Cửa sổ trượt theo phút, cấu hình qua `EVAL_RATE_LIMIT_PER_MINUTE` (mặc định 1000) |

---

## 2. Luồng Invalidation tập trung

Được đóng gói thành dịch vụ dùng chung `app/services/ruleset_cache.py`:
- Hàm `invalidate(env_id)` thực hiện đồng thời:
  1. `pool.delete(f"ruleset:{env_id}")` — Xóa cache cũ.
  2. `pool.publish(f"flagops:ruleset:{env_id}", str(env_id))` — Phát sự kiện cho SDK và Stream hub.
- Tích hợp trực tiếp vào `bump_ruleset_version(db, env_id)` trong `app/services/flag.py`. Do các slice trước (S04, S06, S07) đều gọi `bump_ruleset_version`, mọi cập nhật Flag, Variation, Setting, Targeting Rule hay Segment đều tự động kích hoạt xóa cache và publish sự kiện.

---

## 3. Cơ chế Fallback & Fail-Open (Bảo vệ hệ sinh thái)

Đảm bảo Redis chết **không làm gián đoạn** hoạt động của hệ thống:
1. **Redis Down**: Bọc toàn bộ thao tác trong `try/except (RedisError, OSError)`. Khi có lỗi kết nối hoặc timeout (2s):
   - Ghi log `WARNING`.
   - Đọc trực tiếp từ PostgreSQL và trả về kết quả `200 OK`.
2. **Fail-Open Rate Limit**: Nếu Redis không khả dụng, hàm `check_rate_limit()` trả về `(True, limit)` kèm log cảnh báo, không chặn request hợp lệ của người dùng.
3. **Biến môi trường `REDIS_ENABLED=false`**: Hỗ trợ môi trường local dev hoặc CI tối giản không có container Redis. `get_redis_pool()` trả về `None`, toàn bộ hệ thống fallback về database an toàn.

---

## 4. Rate Limiting & REST Contract

- Dependency `enforce_rate_limit` gắn trên router `/eval/v1` (`/ruleset`, `/flags/{flag_key}/evaluate`, `/flags/evaluate-all`, `/events`).
- Vượt ngưỡng cấu hình:
  - Mã lỗi HTTP: `429 Too Many Requests`.
  - Body lỗi chuẩn RFC/FlagOps error envelope: `code = "RATE_LIMITED"`.
  - Headers phản hồi: `Retry-After: 60`, `X-RateLimit-Remaining: 0`.
- Không hardcode các hằng số trong mã nguồn; sử dụng thuộc tính từ Pydantic `Settings`.

---

## 5. Kết quả kiểm thử Definition of Done

### A. Bộ kiểm thử Integration Redis (`app/tests/integration/test_redis.py`):
```bash
$ docker compose exec -T api pytest app/tests/integration/test_redis.py -v
```
**Kết quả: 6 passed (100% pass rate):**
1. `test_cache_miss_then_hit`: Lần 1 nạp từ DB (đo bằng `QueryCounter`), ghi cache Redis; lần 2 cache hit và số lượng query DB giảm rõ rệt.
2. `test_flag_change_invalidates_cache`: Thay đổi cấu hình cờ (`enabled: False → True`) kích hoạt xóa key Redis, lần gọi sau nạp lại dữ liệu mới từ DB.
3. `test_pubsub_subscriber_receives_message`: Subscriber lắng nghe channel nhận đúng `environment_id` khi hàm invalidation được gọi.
4. `test_rate_limit_exceeded_returns_429`: Vượt ngưỡng request trong 1 phút trả về `429`, mã `RATE_LIMITED` và đầy đủ header `Retry-After`, `X-RateLimit-Remaining`.
5. `test_redis_down_api_still_returns_200`: Giả lập sự cố Redis sập (connection error), API vẫn phản hồi `200 OK` từ DB kèm log warning.
6. `test_redis_disabled_evaluation_passes`: Thiết lập `REDIS_ENABLED=false`, toàn bộ luồng evaluation chạy độc lập hoàn hảo.

---

### B. Kiểm thử thủ công dừng/bật Redis thật (Container Outage Simulation):
```bash
# 1. Gọi khi Redis đang chạy:
$ curl.exe -i -H "X-FlagOps-Key: fo_srv_..." http://localhost:8000/eval/v1/ruleset
HTTP/1.1 200 OK
ETag: "0"
{"rulesetVersion":0,"flags":{},"segments":{}}

# 2. Dừng Redis container:
$ docker compose stop redis
Container flagops-redis Stopped

# 3. Gọi lại ngay sau khi Redis dừng:
$ curl.exe -i -H "X-FlagOps-Key: fo_srv_..." http://localhost:8000/eval/v1/ruleset
HTTP/1.1 200 OK
ETag: "0"
{"rulesetVersion":0,"flags":{},"segments":{}}
# Log container ghi nhận:
# Redis rate limit check failed: Connection closed by server.
# Redis cache read failed: Timeout connecting to server

# 4. Khởi động lại Redis container:
$ docker compose start redis
Container flagops-redis Started

# 5. Gọi lại sau khi phục hồi:
$ curl.exe -i -H "X-FlagOps-Key: fo_srv_..." http://localhost:8000/eval/v1/ruleset
HTTP/1.1 200 OK
```

---

### C. Toàn bộ Test Suite hồi quy (Regression Test):
```bash
$ docker compose exec -T api pytest
```
**Kết quả: 192 passed** — không làm hỏng bất kỳ test nào từ Slice 1 đến Slice 7.

---

### D. Kiểm tra Code Quality & Static Analysis:
```bash
$ docker compose exec -T api ruff check .
All checks passed!

$ docker compose exec -T api mypy app
Success: no issues found in 72 source files
```
