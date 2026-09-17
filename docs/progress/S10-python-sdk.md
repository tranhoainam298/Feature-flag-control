# Progress Report — Slice 10: Python SDK

**Ngày hoàn thành:** 2026-09-17  
**Trạng thái:** HOÀN THÀNH (100% tiêu chí Definition of Done)  
**Kỹ năng áp dụng:** `python-sdk-design`, `evaluation-engine-purity`, `python-testing-pytest`, `ponytail`, `tdd`

---

## 1. Mục tiêu Slice 10

Xây dựng thư viện client chính thức **FlagOps Python SDK** (`flagops`) tại thư mục `sdk/python/`. SDK là một package độc lập, có thể đóng gói và phát hành qua PyPI, phục vụ các ứng dụng Python khác tích hợp kiểm soát Feature Flag và cấu hình ứng dụng (Config Center).

Các cấu phần cốt lõi:
- `sdk/python/flagops/__init__.py`: Export các lớp và kiểu dữ liệu công khai.
- `sdk/python/flagops/client.py`: Lớp `FlagOpsClient` chính.
- `sdk/python/flagops/cache.py`: `RulesetCache` lưu trữ ruleset trong bộ nhớ, thread-safe.
- `sdk/python/flagops/transport.py`: HTTP client (`httpx`), hỗ trợ ETag/304, timeout, exponential backoff có jitter.
- `sdk/python/flagops/streaming.py`: Interface / stub SSE subscriber.
- `sdk/python/flagops/events.py`: `EventBatcher` thu thập sự kiện đánh giá và xả định kỳ (flush).
- `sdk/python/flagops/errors.py`: Exception nội bộ (không bao giờ ném ra ngoài).
- `sdk/python/flagops/engine/`: Engine đánh giá thuần, chia sẻ đồng nhất 100% với backend.
- `sdk/python/tests/`: Bộ kiểm thử toàn diện (29 tests, 89% coverage).

---

## 2. Các nguyên tắc cốt lõi đã hiện thực

### 2.1. Hai chế độ vận hành (Modes)
- **`mode="in_process"` (Mặc định)**:
  - Tải ruleset từ `/eval/v1/ruleset` khi khởi tạo và duy trì luồng polling nền theo chu kỳ `polling_interval` (sử dụng header `If-None-Match` để nhận `304 Not Modified`).
  - Mọi thao tác đánh giá cờ (`is_enabled`, `get_boolean`, `get_string`, `get_number`, `get_json`, `get_variant`) diễn ra hoàn toàn cục bộ trong memory với độ trễ micro-giây (< 0.1ms), **không thực hiện gọi mạng mỗi lần đánh giá**.
  - Đã kiểm chứng: 1000 lần gọi `is_enabled` chỉ phát sinh đúng **1 request duy nhất** tới máy chủ.
- **`mode="remote"`**:
  - Gửi yêu cầu đánh giá trực tiếp tới endpoint `POST /eval/v1/flags/{key}/evaluate` trên server.

### 2.2. Kiến trúc Fail-Safe Tuyệt đối (Bảo vệ ứng dụng khách)
- **CẤM ném exception**: Tất cả các hàm `is_enabled` và `get_*` được bọc trong khối an toàn, luôn trả về giá trị fallback `default` khi có lỗi (lỗi mạng, server trả 500, cờ không tồn tại, v.v.).
- **Chưa từng kết nối được server**: Trả về `default`, ghi log warning đúng **1 lần duy nhất** (chống log spam).
- **Mất kết nối khi đã có cache**: Tiếp tục sử dụng ruleset trong cache cuối cùng, tuyệt đối **không tắt hết flag**.
- **Mọi network call có timeout**: Mặc định `timeout=2.0s`.
- **Exponential Backoff có Jitter**: Dãy thời gian chờ `[1, 2, 4, 8, 16, 32, 60]` giây (cap tại 60s) kèm jitter ngẫu nhiên `±20%`.

### 2.3. Thread Safety & In-memory Cache
- `RulesetCache` sử dụng `threading.RLock` để bảo vệ tài nguyên khi có nhiều luồng đọc/ghi đồng thời.
- Kiểm thử luồng: 10 threads đọc liên tục song song với 1 thread ghi cập nhật version ruleset mới -> hoạt động mượt mà, **không phát sinh bất kỳ ngoại lệ nào**.

### 2.4. Telemetry & Event Batching
- Mỗi lần đánh giá cờ ghi nhận một sự kiện `EvalEvent` vào buffer.
- Luồng nền tự động gửi batch lên `POST /eval/v1/events` mỗi 10 giây hoặc khi buffer đầy 100 sự kiện.
- Khi ứng dụng gọi `client.close()` hoặc kết thúc context manager `with FlagOpsClient(...)`, toàn bộ sự kiện còn lại trong buffer được flush đầy đủ.

### 2.5. Tái sử dụng Engine & Parity Testing
- Engine thuần từ `backend/app/engine/` được vendor đồng bộ sang `sdk/python/flagops/engine/`.
- Test tự động [`tests/test_engine_parity.py`](file:///d:/python/feature%20flag/sdk/python/tests/test_engine_parity.py) đối chiếu từng byte nội dung mã nguồn giữa 2 bên, đảm bảo độ khớp tuyệt đối 100%.

---

## 3. Kết quả Kiểm thử (Definition of Done)

### 3.1. Chạy Pytest & Độ bao phủ Coverage
```bash
$ cd sdk/python && pytest -v --cov=flagops --cov-report=term-missing

Name                          Stmts   Miss  Cover   Missing
-----------------------------------------------------------
flagops\__init__.py               4      0   100%
flagops\cache.py                 80      2    98%   53, 146
flagops\client.py               153     15    90%   38, 41-42, 130, 155, 186, 224-227, 255-274, 305, 361
flagops\engine\__init__.py        6      0   100%
flagops\engine\bucketing.py      35      4    89%   56-57, 62, 89
flagops\engine\evaluator.py      31      2    94%   100-101
flagops\engine\matcher.py        57     16    72%   47-57, 113-115, 125, 133, 148-151
flagops\engine\operators.py     123     18    85%   30, 40, 43-44, 57, 77, 85, 93, 101, 108, 152-153, 165, 173, 181, 189, 197, 205
flagops\engine\types.py         119      0   100%
flagops\errors.py                 8      0   100%
flagops\events.py                46      6    87%   74-75, 80-83
flagops\streaming.py             19      2    89%   37, 41
flagops\transport.py             84     19    77%   81-82, 98-99, 112-113, 116, 123-124, 129, 139-141, 148-149, 162-163, 169-170
-----------------------------------------------------------
TOTAL                           765     84    89%
============================= 29 passed in 2.62s ==============================
```
**Kết quả: 29/29 passed (100%), Coverage đạt 89% (vượt mức yêu cầu >= 85%).**

### 3.2. Danh sách các bài kiểm thử chính đã pass:
1. `test_is_enabled_with_mock_ruleset`: Đánh giá cờ chính xác với ruleset mẫu.
2. `test_get_typed_variants`: Lấy giá trị chuỗi, số, JSON, variant key và EvaluationResult.
3. `test_in_process_mode_1000_evaluations_calls_server_once`: 1000 lượt đánh giá chỉ gọi server 1 lần duy nhất.
4. `test_server_returns_500_continues_using_cached_ruleset`: Server gặp lỗi 500 khi polling, client vẫn phục vụ bình thường từ cache.
5. `test_never_connected_returns_default_without_raising`: Server chết ngay từ đầu, client trả về default an toàn, không raise exception.
6. `test_etag_304_keeps_cache_unchanged`: Server trả 304 Not Modified, client giữ nguyên cache.
7. `test_remote_mode_evaluates_via_api`: Chế độ remote gọi API trực tiếp.
8. `test_get_config_namespace`: Đọc cấu hình namespace từ Config Center.
9. `test_context_manager_syntax`: Hỗ trợ cú pháp `with FlagOpsClient(...) as client:`.
10. `test_calculate_backoff_delay`: Dãy backoff `1, 2, 4, 8, 16, 32, 60` với jitter ±20%.
11. `test_event_batcher_close_flushes_remaining`: Xả toàn bộ sự kiện khi close.
12. `test_concurrent_reads_and_cache_updates`: 10 threads đọc đồng thời trong khi 1 thread ghi cập nhật cache.
13. `test_engine_source_code_identical_parity`: Đối chiếu mã nguồn engine khớp 100% với backend.
14. `test_sdk_integration_with_live_server`: Kiểm thử end-to-end với máy chủ backend Docker đang chạy thật.

### 3.3. Kiểm thử Toàn bộ Hệ thống (Zero Regression)
```bash
$ docker compose exec -T api pytest
======================= 212 passed, 2 warnings in 55.75s =======================

$ docker compose exec -T api ruff check .
All checks passed!

$ docker compose exec -T api mypy app
Success: no issues found in 80 source files
```

---

## 4. Tài liệu Hướng dẫn Sử dụng (10 Dòng Code)

File [`sdk/python/README.md`](file:///d:/python/feature%20flag/sdk/python/README.md):

```python
from flagops import FlagOpsClient

client = FlagOpsClient(api_key="fo_srv_your_api_key", base_url="https://flagops.example.com")

if client.is_enabled("new-checkout", context={"userId": "user-123", "plan": "pro"}, default=False):
    print("New checkout enabled!")

banner = client.get_string("banner-color", default="blue")
config = client.get_config("billing-service")

client.close()
```
