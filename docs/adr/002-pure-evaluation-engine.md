# ADR-002: Kiến trúc Pure Evaluation Engine (Zero-I/O, Deterministic, Portable)

## Trạng thái
Accepted

## Ngày
2026-09-16

## Ngữ cảnh (Context)
Trái tim của hệ thống FlagOps là bộ máy đánh giá cờ tính năng (Evaluation Engine). Trong các hệ thống feature flag hiện đại, engine cần phải phục vụ hàng triệu lượt đánh giá mỗi giây với độ trễ ở mức microsecond ($\mu s$).

Nếu đặt bất kỳ thao tác I/O nào (truy vấn database, đọc Redis, gọi HTTP, hoặc đọc đồng hồ hệ thống `datetime.now()`) vào bên trong engine, hệ thống sẽ gặp các vấn đề nghiêm trọng:
1. **Suy giảm hiệu năng**: Mỗi lần gọi `evaluate()` bị nghẽn bởi I/O mạng hoặc database.
2. **Thiếu tính xác định (Non-deterministic)**: Kết quả đánh giá bị ảnh hưởng bởi trạng thái bên ngoài hoặc độ trễ mạng.
3. **Không thể tái sử dụng (Portability)**: SDK in-process phía client/backend của người dùng và Relay Proxy sẽ không thể dùng lại engine nếu engine bị gắn chặt vào SQLAlchemy, Redis hay FastAPI.

## Quyết định (Decision)
Chúng tôi quyết định thiết kế toàn bộ package `backend/app/engine/` theo mô hình **Hàm thuần khiết (Pure Function)**:

$$\text{evaluate}(\text{ruleset}, \text{context}) \longrightarrow \text{EvaluationResult}$$

### 1. Nguyên tắc Bất di Bất dịch
- **Zero-I/O**: Tuyệt đối không import `sqlalchemy`, `redis`, `httpx`, `fastapi`, `app.models`, `app.services`, `random`, hay `os.environ`.
- **Dữ liệu nạp sẵn (In-Memory Pre-loaded)**: Toàn bộ cờ, cấu hình môi trường, luật mục tiêu và segment phải được biên dịch thành cấu trúc dữ liệu bộ nhớ (`Ruleset`) ở tầng service trước khi chuyển cho engine.
- **Tính bất biến (Immutability)**: Toàn bộ các kiểu dữ liệu của engine được khai báo bằng `dataclass(frozen=True)` và `Enum` tiêu chuẩn của thư viện chuẩn Python. Không dùng Pydantic ở tầng này để giữ engine độc lập hoàn toàn với web framework.

### 2. Thứ tự đánh giá bất biến (Evaluation Pipeline)
Engine bắt buộc tuân theo thứ tự 5 bước tuần tự, không bao giờ thay đổi:
```
1. FLAG_NOT_FOUND  --> Flag không có trong ruleset       -> (default_value, ERROR, FLAG_NOT_FOUND)
2. DISABLED        --> flag_setting.enabled == False     -> (off_variation.value, DISABLED)
3. OVERRIDE        --> Individual override khớp context  -> (override.value, TARGETING_MATCH)
4. TARGETING RULES --> Duyệt rules theo priority ASC:
                         Rule đầu tiên khớp -> DỪNG NGAY (Short-circuit):
                           - 1 variation (weight 100%) -> (value, TARGETING_MATCH)
                           - nhiều variations          -> bucket() -> (value, SPLIT)
5. DEFAULT         --> Không rule nào khớp               -> (default_variation.value, DEFAULT)
```

### 3. Cây điều kiện AND / OR và Giới hạn độ sâu
- Duyệt đệ quy cây điều kiện AND/OR hỗ trợ lồng nhau không giới hạn cấu trúc.
- **Giới hạn độ sâu 5 tầng**: Ngăn chặn tấn công làm tràn call stack (Call Stack Overflow DoS). Vượt quá 5 tầng ném `ConditionDepthExceeded`.
- **Tham chiếu Segment (IS_ONE_OF_SEGMENT)**: Tra cứu segment đã nạp sẵn trong ruleset, hỗ trợ đệ quy segment tối đa 3 tầng (`SegmentDepthExceeded`).

### 4. An toàn khi thiếu thuộc tính
Nếu `context` không chứa thuộc tính mà điều kiện yêu cầu, điều kiện đó tự động trả về `False` (riêng toán tử `NOT_EXISTS` trả về `True`). Tuyệt đối không ném lỗi làm gián đoạn luồng thực thi của ứng dụng tích hợp.

## Phương án thay thế (Alternatives Considered)

| Phương án | Ưu điểm | Nhược điểm | Lý do không chọn |
|---|---|---|---|
| **Engine bất đồng bộ (async) truy vấn DB trực tiếp** | Code dịch vụ ban đầu viết nhanh, không cần biên dịch ruleset | Mỗi lệnh đánh giá tốn kết nối DB (pool exhaustion), độ trễ 5-20ms, không thể đưa vào SDK in-process | Vi phạm yêu cầu hiệu năng cao và chuẩn OpenFeature |
| **Dùng Pydantic Models cho Engine Types** | Tự động parse và validate kiểu dữ liệu | Overhead khởi tạo và kiểm tra schema của Pydantic làm chậm tốc độ đánh giá so với `dataclass(frozen=True)`; phụ thuộc thư viện bên ngoài | Giữ engine tối giản (`ponytail`) và đạt tốc độ thực thi tối đa |
| **Duyệt hết mọi rule rồi mới chọn** | Có thể tổng hợp nhiều rule | Kết quả mơ hồ, khó giải thích (non-deterministic) khi các rule mâu thuẫn biến thể | Trái với nguyên tắc ưu tiên rõ ràng (Priority ASC) |

## Hệ quả (Consequences)
- **Tích cực**:
  - Tốc độ thực thi cực đại: hàng trăm nghìn lần đánh giá mỗi giây trên một nhân CPU.
  - Mã nguồn engine hoàn toàn di động: cùng một file `evaluator.py`, `matcher.py`, `bucketing.py`, `operators.py`, `types.py` có thể đóng gói thẳng vào thư viện `flagops-python-sdk` cho client.
  - Khả năng kiểm thử hoàn hảo: 100% test case là unit test trong bộ nhớ, không cần mock database/redis, thời gian chạy toàn bộ 107 tests engine chỉ mất ~1.5 giây.
- **Thách thức**: Tầng service (API/Background) chịu trách nhiệm tải, cache và biên dịch ruleset đầy đủ cùng cơ chế vô hiệu hóa cache (Redis Pub/Sub) khi có thay đổi cấu hình.
