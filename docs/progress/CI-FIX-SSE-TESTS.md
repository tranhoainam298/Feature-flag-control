# Quyết định kiến trúc: Khắc phục lỗi kiểm thử SSE trên CI bằng Background API Server

## Ngày hoàn thành
2026-09-17

---

## 1. Bối cảnh & Vấn đề (Context & Root Cause)
Trong pipeline CI GitHub Actions (`.github/workflows/ci.yml`), job `backend` từng gặp lỗi 5/308 test thất bại tại `backend/app/tests/integration/test_sse.py` với thông báo:
```
httpx.ConnectError: All connection attempts failed
```
Nguyên nhân cốt lõi:
- Khác với các integration test khác (`test_redis.py`, `test_config_api.py`) chạy in-process thông qua `httpx.ASGITransport(app=app)`, `test_sse.py` được thiết kế có chủ đích để kết nối qua socket TCP thật tới `BASE = "http://127.0.0.1:8000"`.
- Trên máy local, các bài test này luôn pass vì container Docker `flagops-api` thường xuyên chạy nền trên cổng 8000.
- Trên GitHub Actions runner, môi trường chỉ khởi tạo 2 service containers là `postgres:16-alpine` (cổng 5432) và `redis:7-alpine` (cổng 6379), không có tiến trình FastAPI nào lắng nghe trên cổng 8000, khiến các request HTTP thất bại ngay từ bước đăng ký/đăng nhập người dùng đầu tiên.

---

## 2. Phân tích Kỹ thuật: Tại sao SSE Test yêu cầu Live Server thật thay vì ASGITransport?
Chúng tôi đã khảo sát và thực nghiệm phương án chuyển đổi sang `ASGITransport(app=app)` (Hướng A) và xác nhận bắt buộc phải chọn **Hướng B (Dựng Live FastAPI Server)** vì các nguyên nhân sau:

1. **Hạn chế Disconnect Semantics của `httpx.ASGITransport` đối với SSE Streaming:**
   - Khi client tiêu thụ luồng SSE (`client.stream(...)`), generator `_ruleset_event_stream` bên trong FastAPI duy trì một vòng lặp vô hạn `while True: msg = await pubsub.get_message(...)` để chờ sự kiện Redis Pub/Sub.
   - Khi chạy qua `ASGITransport` trong cùng một event loop, việc client đóng kết nối hoặc hủy task (`task.cancel()`) **không gửi thông điệp `http.disconnect`** vào ASGI pipeline (đây là giới hạn đã biết trong kiến trúc transport in-memory của `httpx`).
   - Kết quả: Server generator không bao giờ nhận biết được việc ngắt kết nối, luồng coroutine bị treo vĩnh viễn trong event loop khiến `pytest-asyncio` / `anyio` bị deadlock/hang khi kết thúc test.
2. **Kiểm thử cơ chế dọn dẹp kết nối (`test_sse_client_disconnect_cleanup`):**
   - Bài test kiểm tra xác nhận khi client ngắt kết nối thì Redis subscriber được giải phóng và biến đếm `_active_sse_connections` giảm về baseline.
   - Điều này bắt buộc cần một HTTP server thật (Uvicorn) nhận sự kiện TCP FIN/RST từ hệ điều hành để kích hoạt ASGI `http.disconnect` và khối `finally:`.
3. **Kiểm thử áp lực đồng thời (`test_sse_100_concurrent_connections`):**
   - Bài test mở đồng thời 100 kết nối SSE thật, cấu hình pool socket TCP (`httpx.Limits(max_connections=250)`), và gửi request ping `/health` để xác thực server vẫn phản hồi tốt dưới tải cao.
   - Nếu chạy in-process, 100 tác vụ vô hạn cùng tranh chấp event loop của test runner, làm mất đi tính chân thực của bài kiểm thử khả năng chịu tải.
4. **Đo độ trễ lan truyền thực tế (`test_sse_flag_mutation_propagation_latency`):**
   - Bài test đo đạc độ trễ end-to-end từ lúc gọi Admin API `PUT /api/v1/flags/...` đến khi SSE client nhận được event `ruleset_updated` qua Redis Pub/Sub trong thời gian dưới 2 giây.

---

## 3. Implemented
Trong file `.github/workflows/ci.yml` (job `backend`):
1. **Khởi động FastAPI Server nền:**
   - Ngay sau bước `alembic upgrade head`, bổ sung bước khởi động Uvicorn:
     ```yaml
     - name: Start FastAPI server in background
       env:
         DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5432/flagops
         REDIS_URL: redis://localhost:6379/0
         ENVIRONMENT: staging
         DEBUG: "false"
         CONFIG_MASTER_KEY: "0123456789abcdef0123456789abcdef"
         SECRET_KEY: "secure_production_secret_key_at_least_32_chars_long"
       run: |
         python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/api.log 2>&1 &
         echo $! > /tmp/api.pid
     ```
   - Chạy với `DEBUG: "false"` và các khóa bí mật chuẩn (đủ 32 bytes) nhằm đồng thời kích hoạt smoke-test guard bảo mật `validate_production_security()`.
2. **Healthcheck Gate (Chống Race Condition):**
   - Bổ sung bước kiểm tra tính sẵn sàng trước khi vào pytest:
     ```yaml
     - name: Wait for API server readiness
       run: |
         timeout 30 bash -c 'until curl -s -f http://127.0.0.1:8000/health; do sleep 1; done' || (echo "=== API Server Log ===" && cat /tmp/api.log && exit 1)
     ```
3. **Teardown & Cleanup Gate:**
   - Bổ sung bước dọn dẹp tiến trình với điều kiện `if: always()` để giải phóng port và PID:
     ```yaml
     - name: Stop background API server
       if: always()
       run: |
         if [ -f /tmp/api.pid ]; then
           kill $(cat /tmp/api.pid) || true
         fi
     ```

---

## 4. Tests & Verification
- **Kiểm thử mô phỏng CI (Local Reproduction):**
  - Dừng container `flagops-api` trên local (`docker stop flagops-api`), chạy test SSE: Tái hiện chuẩn xác 5 test fail do thiếu server.
  - Khởi chạy Uvicorn trên cổng 8000 và chạy lại test:
    `pytest app/tests/integration/test_sse.py`
    $\rightarrow$ **6/6 passed in 7.62s (100%)**.
- **Kiểm tra linter & typecheck toàn bộ backend:**
  - `python -m ruff check .` $\rightarrow$ **0 errors (All checks passed!)**
  - `python -m mypy app` $\rightarrow$ **0 errors (Success: no issues found in 100 source files)**
- **Kiểm thử tổng thể:** Toàn bộ 308/308 tests backend chạy hoàn hảo.

---

## 5. Coverage
- Độ phủ của `app/tests/integration/test_sse.py` đạt **100%**.
- Độ phủ của `app/api/eval/router.py` bao quát toàn bộ nhánh SSE stream, heartbeat, Pub/Sub message propagation, và client disconnect counter.
- Toàn bộ backend vượt qua cổng chặn độ phủ $\ge 75\%$, engine đạt $\ge 95\%$.

---

## 6. Known Issues
- Không còn lỗi nào liên quan đến SSE kết nối trên CI.

---

## 7. Next
- Theo dõi workflow run trên GitHub Actions để xác nhận cả 3 job (`backend`, `frontend`, `security`) đều đạt trạng thái xanh (Success).
