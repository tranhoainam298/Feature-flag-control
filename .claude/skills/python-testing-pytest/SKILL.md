---
name: python-testing-pytest
description: >
  Chiến lược test cho FlagOps — pytest, pytest-asyncio, hypothesis, testcontainers.
  Nạp khi viết bất kỳ test nào.
---

# Chiến lược Test FlagOps

## 1. Cấu trúc thư mục test

```
tests/
├── conftest.py            # Fixture dùng chung: db, redis, client, factory
├── unit/
│   ├── engine/            # ★ Coverage ≥ 95%
│   │   ├── test_evaluator.py
│   │   ├── test_matcher.py
│   │   ├── test_bucketing.py
│   │   ├── test_operators.py
│   │   └── test_properties.py   # Hypothesis property tests
│   ├── services/          # Coverage ≥ 80%
│   │   ├── test_flag_service.py
│   │   ├── test_config_service.py
│   │   └── test_auth_service.py
│   └── utils/
├── integration/           # Cần PostgreSQL + Redis (testcontainers)
│   ├── test_flag_api.py
│   ├── test_eval_api.py
│   ├── test_config_api.py
│   └── test_auth_api.py
└── e2e/                   # Playwright (5 luồng chính)
    └── test_scenarios.py
```

## 2. Mục tiêu coverage

| Module | Mục tiêu | Lý do |
|--------|----------|-------|
| `engine/` | ≥ 95% | Trái tim hệ thống, sai thì TẤT CẢ sai |
| `services/` | ≥ 80% | Business logic cốt lõi |
| Tổng thể | ≥ 75% | CI fail nếu dưới ngưỡng |

Lệnh chạy:
```bash
make test            # pytest toàn bộ, fail-under=75
make test-engine     # chỉ engine, fail-under=95
```

## 3. Fixture chuẩn

### Database fixture (testcontainers):
```python
# tests/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture
async def db(postgres_container) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(postgres_container.get_connection_url().replace("psycopg2", "asyncpg"))
    async with AsyncSession(engine) as session:
        yield session
        await session.rollback()
```

### Redis fixture:
```python
from testcontainers.redis import RedisContainer

@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7-alpine") as r:
        yield r
```

### FastAPI test client:
```python
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client(db, redis_container) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

## 4. Ba property test BẮT BUỘC (Hypothesis)

### 4.1 Tính ổn định (Determinism):
```python
from hypothesis import given, strategies as st

@given(user_id=st.text(min_size=1, max_size=64))
def test_bucketing_deterministic(user_id):
    """Cùng đầu vào PHẢI cho cùng kết quả, mọi lúc."""
    dist = [
        DistributionEntry(variation=var_on, weight=50),
        DistributionEntry(variation=var_off, weight=50),
    ]
    result1 = bucket(user_id, "flag-a", "rule-1", dist)
    result2 = bucket(user_id, "flag-a", "rule-1", dist)
    assert result1 == result2
```

### 4.2 Phân bố đều (50/50 sai lệch < 1%):
```python
@given(user_ids=st.lists(st.uuids(), min_size=10000, max_size=10000))
def test_distribution_evenness(user_ids):
    """Rollout 50/50 phải chia gần đều, sai lệch < 1%."""
    dist = [
        DistributionEntry(variation=var_on, weight=50),
        DistributionEntry(variation=var_off, weight=50),
    ]
    results = [bucket(str(u), "flag-a", "rule-1", dist) for u in user_ids]
    ratio = results.count(var_on) / len(results)
    assert 0.49 < ratio < 0.51, f"Tỉ lệ {ratio:.4f} lệch quá 1%"
```

### 4.3 Monotonic (10% ⊆ 20%):
```python
def test_rollout_monotonic():
    """Tăng rollout 10% → 20%: mọi user ở nhóm 10% PHẢI vẫn ở nhóm 20%."""
    users = [f"user-{i}" for i in range(20000)]
    dist_10 = [DistributionEntry(variation=var_on, weight=10),
               DistributionEntry(variation=var_off, weight=90)]
    dist_20 = [DistributionEntry(variation=var_on, weight=20),
               DistributionEntry(variation=var_off, weight=80)]

    group_10 = {u for u in users if bucket(u, "f", "r", dist_10) == var_on}
    group_20 = {u for u in users if bucket(u, "f", "r", dist_20) == var_on}

    assert group_10.issubset(group_20), "Vi phạm monotonic: có user bị mất khi tăng rollout"
```

## 5. Nhóm test bắt buộc cho engine (≥ 60 test)

| # | Nhóm | Số test tối thiểu |
|---|------|-------------------|
| 1 | Flag tắt → off_variation, reason DISABLED | 3 |
| 2 | Không rule → default_variation, reason DEFAULT | 3 |
| 3 | Override cá nhân thắng mọi rule | 5 |
| 4 | Rule priority: rule 1 khớp → rule 2 KHÔNG chạy | 5 |
| 5 | Từng toán tử: mỗi cái ≥ 3 ca (khớp, không khớp, thiếu attr) | 15+ |
| 6 | Điều kiện lồng AND/OR 3 tầng | 5 |
| 7 | Tính ổn định bucketing: 1000 lần → 1000 kết quả giống | 3 |
| 8 | Phân bố đều: 100k userId, rollout 50/50 < 1% sai lệch | 3 |
| 9 | Độc lập giữa flag: 2 flag 10%, tập giao ≈ 1% | 3 |
| 10 | Monotonic: 10% ⊆ 20% | 3 |
| 11 | Regex độc hại → timeout, không treo | 3 |
| 12 | JSON phức tạp làm variation | 3 |
| 13 | Flag not found → ERROR | 3 |
| 14 | Semver operators | 3+ |

## 6. Quy tắc viết test

### CẤM:
```python
# ❌ Test giả chỉ để tăng coverage
def test_something():
    assert True  # CẤM — không kiểm tra hành vi gì

# ❌ Test nhiều hành vi trong một test
def test_everything():
    # Tạo flag, bật flag, đánh giá, kiểm segment, kiểm audit...
    # CẤM — tách thành nhiều test riêng
```

### BẮT BUỘC:
```python
# ✅ Mỗi test kiểm tra MỘT hành vi, tên mô tả rõ
def test_evaluate_returns_disabled_when_flag_is_off():
    """Flag enabled=false PHẢI trả reason=DISABLED và off_variation."""
    ruleset = make_ruleset(enabled=False, off_variation=var_off)
    result = evaluate(ruleset, context)
    assert result.reason == "DISABLED"
    assert result.value == var_off.value

# ✅ Dùng factory/builder để tạo test data
def make_ruleset(*, enabled=True, rules=None, overrides=None, **kwargs) -> Ruleset:
    """Factory function — không copy-paste setup trong mỗi test."""
    ...
```

## 7. Integration test — API

```python
@pytest.mark.asyncio
async def test_evaluate_flag_returns_correct_result(client: AsyncClient, seeded_db):
    response = await client.post(
        "/eval/v1/flags/checkout-v2/evaluate",
        json={"context": {"targetingKey": "user-123", "country": "VN"}, "defaultValue": False},
        headers={"X-FlagOps-Key": "fo_srv_test_key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reason"] in ("TARGETING_MATCH", "SPLIT", "DEFAULT", "DISABLED")
    assert "value" in data
    assert "variant" in data
```

## 8. Pytest config

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "unit: Unit tests (no external dependencies)",
    "integration: Integration tests (needs DB + Redis)",
    "e2e: End-to-end tests (needs full stack)",
]
filterwarnings = ["error"]
```

## 9. Checklist tự kiểm tra

- [ ] Test nằm đúng thư mục (unit/integration/e2e)
- [ ] Mỗi test kiểm tra ĐÚNG MỘT hành vi
- [ ] Tên test mô tả hành vi (`test_X_returns_Y_when_Z`)
- [ ] Không có `assert True` hoặc test rỗng
- [ ] 3 property test bắt buộc đã có (determinism, distribution, monotonic)
- [ ] Engine test ≥ 60, coverage ≥ 95%
- [ ] Integration test dùng testcontainers, không mock DB
- [ ] Factory function cho test data, không copy-paste
- [ ] Đã chạy `make test` trước khi commit
