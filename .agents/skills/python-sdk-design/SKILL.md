---
name: python-sdk-design
description: >
  Quy tắc thiết kế FlagOps Python SDK — cache, polling, SSE, fail-safe, backoff.
  Nạp khi làm sdk/python/.
---

# Thiết kế FlagOps Python SDK

## 1. Kiến trúc SDK

SDK dùng chung module engine (in-process evaluation) — KHÔNG gọi server mỗi lần đánh giá.

```
FlagOpsClient
├── RulesetStore         # Cache ruleset trong memory
├── PollingWorker        # Luồng nền: poll /eval/v1/ruleset mỗi N giây (ETag)
├── SSESubscriber        # Luồng nền: lắng nghe /eval/v1/stream
├── EventBatcher         # Luồng nền: gom evaluation events, flush mỗi 10s
├── Engine (imported)    # Module engine thuần, evaluate(ruleset, context)
└── OpenFeatureProvider  # Adapter cho chuẩn OpenFeature
```

### Vòng đời:
```
init → tải ruleset lần đầu (chặn, có timeout) → sẵn sàng
  ├─ luồng nền: polling mỗi N giây với ETag
  ├─ luồng nền: SSE subscriber, có cập nhật → fetch ngay
  ├─ luồng nền: gom sự kiện đánh giá, flush batch mỗi 10s
  └─ close() → flush nốt sự kiện, đóng kết nối
```

## 2. API công khai

```python
from flagops import FlagOpsClient

client = FlagOpsClient(
    api_key="fo_srv_...",
    base_url="https://flagops.example.com",
    mode="in_process",        # tải ruleset về, đánh giá tại chỗ
    polling_interval=30,       # giây
    enable_streaming=True,     # SSE
    default_timeout=2.0,       # giây, cho mọi network call
)

# Đánh giá flag
if client.is_enabled("checkout-v2",
                     context={"targetingKey": user.id, "country": "VN"},
                     default=False):
    render_new_checkout()

# Lấy string variant
color = client.get_string("banner-color", context=ctx, default="blue")

# Lấy JSON variant
config = client.get_json("ui-config", context=ctx, default={})

# Lấy config
cfg = client.get_config("payment-service")

# Đóng SDK (bắt buộc)
client.close()
```

## 3. Quy tắc an toàn — CẤM ném exception

SDK **TUYỆT ĐỐI KHÔNG ĐƯỢC** ném exception ra ứng dụng khách. Luôn trả default value.

### Ví dụ ĐÚNG:
```python
class FlagOpsClient:
    def is_enabled(self, flag_key: str, context: dict, default: bool = False) -> bool:
        try:
            result = self._evaluate(flag_key, context, default)
            return bool(result.value)
        except Exception as e:
            self._logger.warning(f"Evaluation error for '{flag_key}': {e}")
            self._track_event(flag_key, default, "ERROR")
            return default  # Luôn trả default, KHÔNG ném exception

    def get_string(self, flag_key: str, context: dict, default: str = "") -> str:
        try:
            result = self._evaluate(flag_key, context, default)
            return str(result.value)
        except Exception:
            return default
```

### Ví dụ SAI:
```python
# ❌ Ném exception ra ứng dụng khách — CẤM
def is_enabled(self, flag_key: str, context: dict) -> bool:
    result = self._evaluate(flag_key, context)
    if result.reason == "ERROR":
        raise FlagOpsError("Flag not found")  # CẤM — sẽ crash ứng dụng khách
    return result.value
```

## 4. Mất kết nối → Dùng cache cuối cùng

Khi SDK không kết nối được server:
- **TIẾP TỤC** dùng ruleset cache cuối cùng
- **KHÔNG** tắt hết flag (fail-closed)
- **KHÔNG** trả default cho mọi flag
- Ghi log cảnh báo

### Ví dụ ĐÚNG:
```python
class RulesetStore:
    def __init__(self):
        self._ruleset: Ruleset | None = None
        self._last_updated: float = 0

    def get(self) -> Ruleset | None:
        return self._ruleset  # Trả ruleset cũ nếu chưa cập nhật được

    def update(self, ruleset: Ruleset):
        self._ruleset = ruleset
        self._last_updated = time.monotonic()

class PollingWorker:
    async def _poll(self):
        try:
            new_ruleset = await self._fetch_ruleset()
            self._store.update(new_ruleset)
            self._consecutive_failures = 0
        except Exception as e:
            self._consecutive_failures += 1
            self._logger.warning(
                f"Polling failed ({self._consecutive_failures}x): {e}. "
                f"Using cached ruleset."
            )
            # KHÔNG xóa ruleset cũ, KHÔNG tắt flag
```

### Ví dụ SAI:
```python
# ❌ Mất kết nối → xóa cache → tắt hết flag
except ConnectionError:
    self._store.clear()  # CẤM — sẽ làm mọi flag trả default/off
```

## 5. Exponential Backoff có Jitter

Khi kết nối lại sau lỗi: **1, 2, 4, 8, 16, 32, 60 giây** (cap 60s) + random jitter.

```python
import random

def _next_backoff(self) -> float:
    """Exponential backoff: 1, 2, 4, 8, 16, 32, 60 giây + jitter."""
    base_delays = [1, 2, 4, 8, 16, 32, 60]
    idx = min(self._consecutive_failures, len(base_delays) - 1)
    base = base_delays[idx]
    jitter = random.uniform(0, base * 0.5)  # 0-50% jitter
    return base + jitter
```

## 6. Batch event flush mỗi 10 giây

SDK gom evaluation events và gửi batch mỗi 10 giây (hoặc khi buffer đầy 100 events).

```python
class EventBatcher:
    def __init__(self, flush_interval: float = 10.0, max_buffer: int = 100):
        self._buffer: list[EvalEvent] = []
        self._flush_interval = flush_interval
        self._max_buffer = max_buffer

    def track(self, event: EvalEvent):
        self._buffer.append(event)
        if len(self._buffer) >= self._max_buffer:
            self._flush()

    def _flush(self):
        if not self._buffer:
            return
        events = self._buffer.copy()
        self._buffer.clear()
        try:
            self._api.post("/eval/v1/events", json={"events": [e.to_dict() for e in events]})
        except Exception as e:
            self._logger.warning(f"Event flush failed: {e}")
            # KHÔNG ném exception, sự kiện bị mất thì thôi
```

## 7. close() phải flush nốt

```python
class FlagOpsClient:
    def close(self):
        """Đóng SDK: flush events còn lại, đóng SSE, dừng polling."""
        self._event_batcher.flush()       # Flush nốt events
        self._sse_subscriber.stop()       # Đóng SSE
        self._polling_worker.stop()        # Dừng polling
        self._logger.info("FlagOps SDK closed")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

## 8. Mọi network call có timeout

```python
# Mọi request phải có timeout, default 2 giây
self._http = httpx.Client(timeout=httpx.Timeout(self._default_timeout))
```

KHÔNG để request treo vô hạn. KHÔNG dùng `timeout=None`.

## 9. OpenFeature Provider

```python
# sdk/python/flagops/openfeature.py
from openfeature.provider import AbstractProvider
from openfeature.flag_evaluation import FlagResolutionDetails

class FlagOpsProvider(AbstractProvider):
    def __init__(self, api_key: str, **kwargs):
        self._client = FlagOpsClient(api_key=api_key, **kwargs)

    def resolve_boolean_details(self, flag_key, default_value, context=None):
        result = self._client._evaluate(flag_key, context or {}, default_value)
        return FlagResolutionDetails(
            value=result.value,
            variant=result.variant,
            reason=result.reason,
        )

    # Tương tự cho resolve_string_details, resolve_integer_details, resolve_object_details

    def shutdown(self):
        self._client.close()
```

Ứng dụng khách sử dụng:
```python
from openfeature import api
from flagops.openfeature import FlagOpsProvider

api.set_provider(FlagOpsProvider(api_key="fo_srv_..."))
client = api.get_client()
enabled = client.get_boolean_value("checkout-v2", False, ctx)
```

## 10. Khởi tạo lần đầu — chặn có timeout

```python
class FlagOpsClient:
    def __init__(self, api_key: str, base_url: str, default_timeout: float = 2.0, **kwargs):
        # ...
        # Tải ruleset lần đầu, CHỜ có timeout
        try:
            initial_ruleset = self._fetch_ruleset_sync(timeout=default_timeout)
            self._store.update(initial_ruleset)
            self._ready = True
        except Exception as e:
            self._logger.error(f"Initial ruleset fetch failed: {e}. SDK will use defaults.")
            self._ready = False
            # KHÔNG raise — SDK vẫn hoạt động, trả default cho mọi flag
```

## 11. Checklist tự kiểm tra

- [ ] SDK không ném exception ra ứng dụng khách — luôn trả default
- [ ] Mất kết nối → dùng cache cuối cùng, KHÔNG tắt flag
- [ ] Backoff: 1,2,4,8,16,32,60 giây + jitter
- [ ] Batch event flush mỗi 10s
- [ ] close() flush nốt events trước khi đóng
- [ ] Mọi network call có timeout
- [ ] Khởi tạo lần đầu chặn có timeout, thất bại → vẫn hoạt động
- [ ] Dùng chung module engine (evaluate thuần)
- [ ] OpenFeature Provider implement đầy đủ
- [ ] Context manager (__enter__/__exit__) được hỗ trợ
