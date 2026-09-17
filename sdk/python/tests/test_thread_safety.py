"""Concurrency and thread safety tests for FlagOps SDK."""

import threading
import time
from unittest.mock import MagicMock

from flagops.cache import RulesetCache, parse_ruleset
from flagops.client import FlagOpsClient


def test_concurrent_reads_and_cache_updates(sample_ruleset):
    """Verify 10 threads reading concurrently while 1 thread updates cache causes no errors."""
    cache = RulesetCache()
    initial_ruleset = parse_ruleset(sample_ruleset)
    cache.update(initial_ruleset)

    stop_event = threading.Event()
    exceptions: list[Exception] = []
    read_counts = [0] * 10

    def reader_loop(thread_id: int):
        while not stop_event.is_set():
            try:
                flag = cache.get_flag("checkout-v2")
                if flag is not None:
                    _ = flag.enabled
                read_counts[thread_id] += 1
            except Exception as exc:
                exceptions.append(exc)

    def writer_loop():
        version = 100
        while not stop_event.is_set():
            try:
                payload = dict(sample_ruleset)
                payload["rulesetVersion"] = version
                version += 1
                r = parse_ruleset(payload)
                cache.update(r, etag=f"v{version}")
                time.sleep(0.005)
            except Exception as exc:
                exceptions.append(exc)

    threads: list[threading.Thread] = []
    for i in range(10):
        t = threading.Thread(target=reader_loop, args=(i,), daemon=True)
        threads.append(t)
        t.start()

    writer = threading.Thread(target=writer_loop, daemon=True)
    writer.start()

    # Let concurrent traffic run for 0.5s
    time.sleep(0.5)
    stop_event.set()

    for t in threads:
        t.join(timeout=1.0)
    writer.join(timeout=1.0)

    assert len(exceptions) == 0, f"Thread safety violated with exceptions: {exceptions}"
    assert sum(read_counts) > 1000, "Should have performed thousands of concurrent reads"
