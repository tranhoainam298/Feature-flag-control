---
name: evaluation-engine-purity
description: >
  Quy tắc TUYỆT ĐỐI cho evaluation engine — pure function, không I/O, deterministic.
  Nạp khi động vào bất cứ file nào trong backend/app/engine/.
---

# Evaluation Engine — Quy tắc Purity

## 1. Nguyên tắc cốt lõi

> **Evaluation Engine là hàm thuần (pure function).** Không I/O, không side effect, deterministic.
> Đây là quyết định thiết kế QUAN TRỌNG NHẤT của FlagOps.

Engine phải dùng lại được ở 3 nơi: server, relay proxy, và SDK in-process.
Nếu engine phụ thuộc I/O thì KHÔNG thể tái sử dụng.

## 2. Chữ ký chính

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class EvaluationResult:
    value: Any
    variant: str
    reason: str                    # TARGETING_MATCH | SPLIT | DEFAULT | DISABLED | ERROR
    flag_metadata: dict | None = None

def evaluate(
    ruleset: Ruleset,              # Dữ liệu đã nạp SẴN từ tầng service
    context: EvaluationContext,     # Thuộc tính user: targetingKey, country, plan...
    default_value: Any = None,
) -> EvaluationResult:
    ...
```

**Dùng `dataclass(frozen=True)` cho mọi type trong engine**, KHÔNG dùng Pydantic (vì engine
không phụ thuộc FastAPI/Pydantic).

## 3. DANH SÁCH CẤM IMPORT (TUYỆT ĐỐI)

Các module sau **CẤM XUẤT HIỆN** trong bất kỳ file nào dưới `backend/app/engine/`:

```python
# ❌ CẤM TẤT CẢ CÁC IMPORT SAU TRONG ENGINE
import sqlalchemy          # I/O database
import redis               # I/O cache
import httpx               # I/O network
import requests            # I/O network
import fastapi             # Web framework
import aiohttp             # I/O network
from datetime import datetime  # datetime.now() → non-deterministic
                               # (nhưng ĐƯỢC dùng datetime cho parse/compare)
import random              # Non-deterministic
import os                  # os.environ → external state
import asyncio             # Engine phải đồng bộ (sync), không async
```

### Import ĐƯỢC PHÉP:
```python
import mmh3                # Hash function (pure)
import re                  # Regex (pure, nhưng phải có timeout)
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
from typing import Any
from packaging.version import Version  # Semver compare
```

## 4. Thứ tự đánh giá (KHÔNG ĐỔI)

```
1. FLAG_NOT_FOUND  → flag không tồn tại trong ruleset
2. DISABLED        → flag_setting.enabled == false → trả off_variation
3. OVERRIDE        → individual override khớp context[bucketing_key]
4. RULE            → duyệt targeting rule theo priority, rule đầu tiên match → DỪNG
5. SPLIT           → rule match + distribution có nhiều variation → bucketing
6. DEFAULT         → không rule nào khớp → trả default_variation
```

### Ví dụ ĐÚNG:
```python
def evaluate(ruleset: Ruleset, context: EvaluationContext, default_value: Any = None) -> EvaluationResult:
    flag_setting = ruleset.get_flag_setting(context.flag_key)

    # 1. Flag not found
    if flag_setting is None:
        return EvaluationResult(value=default_value, variant="", reason="ERROR",
                                flag_metadata={"error_code": "FLAG_NOT_FOUND"})

    # 2. Disabled
    if not flag_setting.enabled:
        return EvaluationResult(value=flag_setting.off_variation.value,
                                variant=flag_setting.off_variation.key, reason="DISABLED")

    # 3. Individual override
    bucketing_value = context.get(flag_setting.bucketing_key, context.targeting_key)
    override = flag_setting.get_override(bucketing_value)
    if override is not None:
        return EvaluationResult(value=override.variation.value,
                                variant=override.variation.key, reason="TARGETING_MATCH",
                                flag_metadata={"matched": "individual_override"})

    # 4-5. Targeting rules — ĐÃ SẮP XẾP THEO PRIORITY
    for rule in flag_setting.rules:  # rules đã sort by priority ASC
        if match_conditions(rule, context):
            if len(rule.distribution) == 1 and rule.distribution[0].weight == 100:
                var = rule.distribution[0].variation
                return EvaluationResult(value=var.value, variant=var.key,
                                        reason="TARGETING_MATCH")
            else:
                var = bucket(bucketing_value, context.flag_key, str(rule.id), rule.distribution)
                return EvaluationResult(value=var.value, variant=var.key, reason="SPLIT")

    # 6. Default
    return EvaluationResult(value=flag_setting.default_variation.value,
                            variant=flag_setting.default_variation.key, reason="DEFAULT")
```

### Ví dụ SAI:
```python
# ❌ Engine query DB để lấy segment — PHẢI nhận segment đã nạp sẵn trong ruleset
async def evaluate(flag_key: str, context: dict, db: AsyncSession):
    flag = await db.execute(select(Flag).where(Flag.key == flag_key))  # CẤM!
    segments = await db.execute(select(Segment).where(...))             # CẤM!
```

```python
# ❌ Duyệt TIẾP sau khi đã match rule → kết quả không xác định
for rule in rules:
    if match_conditions(rule, context):
        results.append(rule)  # CẤM — phải DỪNG ngay tại rule đầu tiên match
return results[-1]            # Sai logic hoàn toàn
```

## 5. Reason code hợp lệ

| Reason | Khi nào |
|--------|---------|
| `ERROR` | Flag không tồn tại, type mismatch, parse error |
| `DISABLED` | `enabled == false` |
| `TARGETING_MATCH` | Override cá nhân hoặc rule khớp + 100% một variation |
| `SPLIT` | Rule khớp + distribution nhiều variation (bucketing) |
| `DEFAULT` | Không rule nào khớp |

KHÔNG tự nghĩ thêm reason code ngoài danh sách trên.

## 6. Bucketing (Sticky Percentage Rollout)

```python
import mmh3

def bucket(context_value: str, flag_key: str, rule_id: str,
           distribution: list[DistributionEntry], seed: int = 0) -> Variation:
    hash_input = f"{flag_key}:{rule_id}:{context_value}"
    h = mmh3.hash(hash_input, seed, signed=False)
    bucket_value = h % 10000  # Độ phân giải 0.01%

    cumulative = 0
    for entry in distribution:
        cumulative += entry.weight * 100  # weight tính theo %, nhân 100 cho thang 10000
        if bucket_value < cumulative:
            return entry.variation

    return distribution[-1].variation  # Phòng hờ sai số làm tròn
```

**Tại sao ghép flag_key + rule_id:** tránh tương quan bucket giữa các flag. Nếu chỉ hash userId,
user nào rơi vào phân vị thấp sẽ LUÔN bị chọn ở mọi flag rollout 10%.

**Tại sao 10000 chứ không 100:** độ phân giải 0.01%, cần cho canary ở hệ thống lưu lượng lớn.

## 7. Xử lý thiếu thuộc tính

Nếu `context` không có thuộc tính mà rule yêu cầu → điều kiện đó trả `false` (KHÔNG ném lỗi).

```python
# ĐÚNG
def eval_condition(condition: Condition, context: EvaluationContext) -> bool:
    value = context.get(condition.attribute)
    if value is None:
        return False  # Thiếu thuộc tính → false, không raise
    return apply_operator(condition.operator, value, condition.value)
```

## 8. Regex phải có timeout

```python
import re
import signal

MAX_REGEX_MS = 50  # 50ms timeout

def safe_regex_match(pattern: str, value: str) -> bool:
    try:
        # Dùng re.fullmatch với timeout mechanism
        # Trên production dùng google-re2 hoặc regex module có timeout
        compiled = re.compile(pattern)
        return compiled.fullmatch(value) is not None
    except re.error:
        return False
```

## 9. Giới hạn độ sâu điều kiện

Cây điều kiện JSONB tối đa 5 tầng lồng. Engine PHẢI kiểm tra trước khi đánh giá.

```python
def validate_condition_depth(node: dict, depth: int = 0, max_depth: int = 5) -> bool:
    if depth > max_depth:
        return False
    if "children" in node:
        return all(validate_condition_depth(c, depth + 1, max_depth) for c in node["children"])
    return True
```

## 10. Checklist tự kiểm tra

- [ ] Không có import nào trong danh sách CẤM (mục 3)
- [ ] Tất cả function trong engine là sync (không `async def`)
- [ ] Dùng `dataclass(frozen=True)` cho types, không dùng Pydantic
- [ ] Thứ tự đánh giá đúng: NOT_FOUND → DISABLED → OVERRIDE → RULE → SPLIT → DEFAULT
- [ ] Rule đầu tiên match thì DỪNG ngay, không duyệt tiếp
- [ ] Reason code chỉ dùng 5 giá trị hợp lệ
- [ ] Bucketing ghép flag_key + rule_id + context_value
- [ ] Thiếu thuộc tính → false, không raise
- [ ] Regex có timeout
- [ ] Độ sâu điều kiện tối đa 5
