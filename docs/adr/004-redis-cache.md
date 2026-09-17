# ADR-004: Kiến trúc Redis Cache, Pub/Sub Invalidation và Fail-Open Rate Limiting

## Trạng thái
Accepted

## Ngày
2026-09-17

## Ngữ cảnh (Context)
Đường dẫn đánh giá cờ (Evaluation API - hot path) là khu vực chịu lưu lượng truy cập cao nhất trong hệ thống FlagOps. Mỗi SDK của client hoặc server có thể định kỳ tải ruleset hoặc gửi yêu cầu đánh giá với tần suất hàng nghìn requests/giây.

Nếu mỗi yêu cầu đều truy vấn trực tiếp vào PostgreSQL:
1. **Quá tải Database**: Tắc nghẽn kết nối (connection pool exhaustion), tăng độ trễ và đe dọa sự ổn định của hệ thống.
2. **Không kịp thời cập nhật**: Các SDK và Relay Proxy cần biết ngay khi cờ thay đổi mà không phải liên tục polling DB.
3. **Nguy cơ tấn công DoS / Lạm dụng API key**: Thiếu cơ chế giới hạn lưu lượng (rate limiting) cho từng API key.

Đồng thời, **nguyên tắc cốt lõi của FlagOps là Redis không được trở thành Single Point of Failure (SPOF)**. Nếu Redis gặp sự cố (mất điện, sập mạng, đầy bộ nhớ), ứng dụng bắt buộc phải tiếp tục hoạt động mà không trả về lỗi 500 cho người dùng.

## Quyết định (Decision)

Chúng tôi quyết định tích hợp Redis vào FlagOps phục vụ 3 công dụng chính với kiến trúc **Fail-Open**:

### 1. Ba công dụng chính
1. **Cache Ruleset**:
   - Khóa: `ruleset:{environment_id}`
   - TTL: 300 giây (cấu hình qua `RULESET_CACHE_TTL_SECONDS`).
   - Chỉ lưu trữ bản dịch ruleset của scope `SERVER` để tránh trộn lẫn dữ liệu với `CLIENT` (vốn là tập con).
2. **Pub/Sub Invalidation**:
   - Channel: `flagops:ruleset:{environment_id}`
   - Thông báo phát đi mỗi khi ruleset thay đổi, nội dung mang `environment_id`.
3. **Rate Limiting**:
   - Khóa: `ratelimit:{api_key_id}:{minute}` (sliding window theo từng phút).
   - Ngưỡng cấu hình qua biến môi trường `EVAL_RATE_LIMIT_PER_MINUTE` (mặc định 1000). Không hardcode giá trị trong mã nguồn.
   - Khi vượt ngưỡng: trả về mã `429 Too Many Requests` kèm theo các header chuẩn `Retry-After: 60` và `X-RateLimit-Remaining: 0`.

### 2. Luồng Invalidation tập trung
Mọi thao tác thay đổi Flag, Variation, FlagEnvironmentSetting, Segment hoặc Targeting Rule đều kích hoạt hàm cập nhật phiên bản môi trường:
```
PostgreSQL write → bump_ruleset_version() → DELETE cache key → PUBLISH message
```
Triển khai tập trung trong `app/services/ruleset_cache.py:invalidate(env_id)` và được gọi tự động bên trong `bump_ruleset_version()`.

### 3. Nguyên tắc Fail-Open tuyệt đối (Chống Redis làm chết hệ thống)
Mọi hàm trong `app/services/ruleset_cache.py` đều bọc trong khối `try/except (RedisError, OSError)`:
- **Đọc cache lỗi/Redis sập**: Ghi log `WARNING`, trả về `None`, luồng xử lý tự động rơi xuống đọc trực tiếp PostgreSQL.
- **Ghi cache / Invalidate lỗi**: Ghi log `WARNING` và bỏ qua, không chặn request cập nhật cờ.
- **Rate limit khi Redis sập**: Cho phép request đi qua (`fail-open`, `allowed = True`), ghi log cảnh báo.
- **Tắt Redis hoàn toàn (`REDIS_ENABLED=false`)**: `get_redis_pool()` trả về `None`, hệ thống vận hành trơn tru ở chế độ standalone/dev mà không cần Redis container.

### 4. Quản lý Connection Pool Singleton
Tạo pool dùng chung trong `app/core/redis.py` với cơ chế nhận diện event loop để tương thích hoàn toàn với kiến trúc bất đồng bộ của FastAPI và pytest-asyncio.

## Phương án thay thế (Alternatives Considered)

| Phương án | Ưu điểm | Nhược điểm | Lý do không chọn |
|---|---|---|---|
| **Fail-Closed khi Redis sập (ném 500 / chặn request)** | Đảm bảo tính nhất quán tuyệt đối và bảo vệ API key limit | Redis sập kéo theo toàn bộ ứng dụng chết | Vi phạm nghiêm trọng yêu cầu độ sẵn sàng cao của hệ thống Feature Flag |
| **In-Memory Cache nội bộ trong từng FastAPI worker** | Không cần Redis | Dữ liệu cache phân tán giữa các worker, không đồng bộ khi scale nhiều instance | Khó invalidate chính xác khi có nhiều pod/container |
| **Token Bucket phức tạp bằng Redis Lua Script** | Mịn hơn Fixed Window | Tăng độ phức tạp mã nguồn, khó debug, overhead script execution | Fixed window theo phút (`INCR` + `EXPIRE 60s`) đáp ứng triệt để yêu cầu và tối giản (`ponytail`) |

## Hệ quả (Consequences)
- **Tích cực**:
  - Giảm thiểu hơn 90% số lượng truy vấn đọc vào PostgreSQL trên các route `/eval/v1/ruleset`.
  - Phản hồi tức thời cho các subscriber thông qua Pub/Sub.
  - Bảo vệ hệ thống khỏi lạm dụng API key bằng HTTP 429 và headers chuẩn REST.
  - Khả năng phục hồi cao (fault-tolerant): hệ thống vẫn duy trì 100% chức năng ngay cả khi Redis container bị dừng hoàn toàn.
