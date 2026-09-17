# FlagOps Python SDK

Official Python SDK for the FlagOps Feature Flag and Configuration Management Service.

## Installation

```bash
pip install flagops
```

## Quickstart (10 lines)

```python
from flagops import FlagOpsClient

client = FlagOpsClient(api_key="fo_srv_your_api_key", base_url="https://flagops.example.com")

if client.is_enabled("new-checkout", context={"userId": "user-123", "plan": "pro"}, default=False):
    print("New checkout enabled!")

banner = client.get_string("banner-color", default="blue")
config = client.get_config("billing-service")

client.close()
```

## Features

- **In-process Evaluation**: Sub-millisecond evaluation latency evaluated locally with zero remote network calls on the critical path.
- **Fail-Safe Reliability**: Never throws exceptions to client code during evaluation; falls back gracefully to defaults.
- **Resilient Stale Caching**: If the FlagOps server goes down, continues serving the last valid cached ruleset.
- **Smart Background Polling**: Uses HTTP ETag / 304 Not Modified to minimize bandwidth and CPU overhead.
- **Exponential Backoff**: Automatic retry backoff `[1, 2, 4, 8, 16, 32, 60]` seconds with ±20% jitter.
- **Thread-safe**: Designed for highly concurrent multi-threaded Python applications.
- **Batch Event Telemetry**: Collects flag evaluation metrics and flushes in batches every 10 seconds.
