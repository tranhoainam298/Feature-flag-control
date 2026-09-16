# Progress Report — Slice 5A: Engine Types & Operators

**Ngày hoàn thành:** 2026-09-16  
**Trạng thái:** HOÀN THÀNH (100% tiêu chí Definition of Done)  
**Kỹ năng áp dụng:** `evaluation-engine-purity`, `python-testing-pytest`, `ponytail`, `tdd`

---

## 1. Mục tiêu Slice 5A

Xây dựng nền tảng cốt lõi cho Evaluation Engine của FlagOps:
1. **Types thuần**: `backend/app/engine/types.py` sử dụng `dataclass(frozen=True)` và `Enum` thuần, hoàn toàn không phụ thuộc SQLAlchemy, Pydantic, FastAPI, Redis hay Network.
2. **22 Toán tử điều kiện**: `backend/app/engine/operators.py` hỗ trợ đầy đủ 22 toán tử so khớp, phân giải bằng dispatch table `OPERATORS: dict[str, Callable]`.
3. **Purity & Zero-I/O**: Không I/O, không truy cập database/mạng/đồng hồ hệ thống, không ném exception khi thiếu context attribute.
4. **Bảo vệ chống ReDoS**: Cơ chế timeout 50ms cho `MATCHES_REGEX`.
5. **Độ bao phủ kiểm thử**: Tối thiểu 66 tests (3 ca x 22 toán tử) + kiểm thử ReDoS độc hại + coverage $\ge 95\%$.

---

## 2. Các thực thể và kiểu dữ liệu (`backend/app/engine/types.py`)

| Kiểu / Thực thể | Định nghĩa | Mô tả & Tuân thủ |
|---|---|---|
| `Reason` | `str, Enum` | 7 lý do chuẩn: `TARGETING_MATCH`, `SPLIT`, `DEFAULT`, `DISABLED`, `ERROR`, `STATIC`, `CACHED` |
| `ErrorCode` | `str, Enum` | Mã lỗi chuẩn: `FLAG_NOT_FOUND`, `TYPE_MISMATCH`, `PARSE_ERROR`, `GENERAL_ERROR`, `INVALID_CONTEXT`, `TARGETING_KEY_MISSING` |
| `Operator` | `str, Enum` | 22 toán tử so khớp |
| `EvaluationContext` | `dataclass(frozen=True)` | Chứa `targeting_key` và `attributes: dict[str, Any]`. Cung cấp phương thức `get(key, default)` an toàn, tra cứu cả `targetingKey` |
| `Variation` | `dataclass(frozen=True)` | `key`, `value`, `id`, `name`, `description` |
| `Condition` | `dataclass(frozen=True)` | `attribute`, `operator`, `value` |
| `ConditionGroup` | `dataclass(frozen=True)` | `operator` ("AND" / "OR"), `conditions: list[Condition]`, `children: list[ConditionGroup]` |
| `DistributionEntry` | `dataclass(frozen=True)` | `variation`, `weight` (phần trăm) |
| `TargetingRule` | `dataclass(frozen=True)` | `id`, `priority`, `conditions`, `distribution`, `segment_id`, `description` |
| `IndividualOverride` | `dataclass(frozen=True)` | `context_key`, `variation`, `id` |
| `FlagRuleset` | `dataclass(frozen=True)` | Ruleset của một flag trong môi trường cụ thể |
| `Ruleset` | `dataclass(frozen=True)` | Toàn bộ ruleset của môi trường (`environment_id`, `ruleset_version`, `flags`, `segments`) |
| `EvaluationResult` | `dataclass(frozen=True)` | Kết quả đánh giá: `value`, `variant`, `reason`, `flag_metadata`, `error_code`, `error_message` |

---

## 3. Bảng 22 Toán tử điều kiện (`backend/app/engine/operators.py`)

| Nhóm | Toán tử | Kiểu dữ liệu | Quy ước xử lý |
|---|---|---|---|
| **So sánh** | `EQ`, `NEQ` | Mọi kiểu | So sánh bool chặt chẽ (`True != 1`); ép về `Decimal` nếu là số/chuỗi số; fallback về chuỗi |
| **Thứ tự số** | `GT`, `GTE`, `LT`, `LTE` | Số, chuỗi số | Ép an toàn về `Decimal`, không dùng float trần. Giá trị không hợp lệ trả `False` |
| **Tập hợp** | `IN`, `NOT_IN` | Danh sách, tập hợp | Tìm kiếm trực tiếp hoặc qua set chuỗi để đạt $O(1)$ |
| **Chuỗi** | `CONTAINS`, `NOT_CONTAINS` | Chuỗi | Kiểm tra chuỗi con qua `in` / `not in` |
| **Đầu / Cuối** | `STARTS_WITH`, `ENDS_WITH` | Chuỗi | Dùng `.startswith()` và `.endswith()` |
| **Regex** | `MATCHES_REGEX`, `NOT_MATCHES_REGEX` | Chuỗi | Dùng `regex.search(..., timeout=0.05)`. Bắt lỗi cú pháp regex và timeout an toàn |
| **Semver** | `SEMVER_EQ`, `SEMVER_NEQ`, `SEMVER_GT`, `SEMVER_GTE`, `SEMVER_LT`, `SEMVER_LTE` | Phiên bản | Dùng thư viện `packaging.version.Version`. Phiên bản không hợp lệ trả `False` |
| **Tồn tại** | `EXISTS`, `NOT_EXISTS` | Mọi kiểu | `EXISTS`: `context_value is not None`. `NOT_EXISTS`: `context_value is None` |

---

## 4. ADR ngắn: Lựa chọn cơ chế Timeout 50ms cho Regex (Chống ReDoS)

- **Vấn đề**: Các biểu thức chính quy phức tạp hoặc độc hại (ví dụ `(a+)+$`) có thể gây ra hiện tượng Catastrophic Backtracking (ReDoS), làm nghẽn luồng tính toán CPU của tiến trình evaluate cờ tính năng.
- **Phương án cân nhắc**:
  1. *Chạy trong Thread/ThreadPoolExecutor với timeout*: Nhược điểm là chi phí overhead khởi tạo context thread (~1ms/lần gọi) làm giảm throughput của engine; quan trọng hơn, luồng C chạy `re.search` trong Python không thể bị hủy ngay lập tức, vẫn tiếp tục đốt CPU 100% trong background.
  2. *Dùng module C `regex` với tham số `timeout=0.05`*: Kiểm tra timeout trực tiếp bên trong vòng lặp backtracking ở tầng mã nguồn C, giải phóng CPU ngay lập tức khi chạm mốc 50ms mà không cần sinh thêm thread hoặc process.
- **Quyết định**: Chọn module `regex` với cờ `timeout=0.05`. Đảm bảo synchronous, zero-I/O, an toàn tuyệt đối trước ReDoS.

---

## 5. Kết quả kiểm thử & Đo đạc

### Unit Tests
- **Số lượng test**: **71 tests** (vượt yêu cầu tối thiểu 66 tests).
  - 22 toán tử x 3 ca (Match, No Match, Missing Context) = 66 ca.
  - 1 ca ReDoS độc hại `(a+)+$` trên 50 ký tự `'a'` hoàn thành trong **< 1ms**, và với chuỗi gây backtracking kết thúc trong **< 200ms**, không treo.
  - 4 ca kiểm tra edge cases: dispatch table đủ 22 toán tử, toán tử lạ trả `False`, toán tử rỗng/None, semver/decimal invalid.
- **Thời gian chạy**: ~0.68s.

### Code Coverage
- File `backend/app/engine/operators.py`:
  - Tổng số câu lệnh: **123**
  - Số lệnh chưa duyệt: **0**
  - Tỷ lệ bao phủ (Coverage): **100%** (Vượt xa chỉ tiêu $\ge 95\%$).

### Kiểm tra tính tinh khiết (Purity Check)
```bash
grep -rn "import sqlalchemy\|import redis\|from fastapi\|from app.models" backend/app/engine/
# Kết quả: 0 kết quả (Exit code 1, không có vi phạm nào)
```

### Toàn bộ hệ thống (Regression Test)
- Tổng cộng: **125/125 tests passed (100%)**.
- Linting: `ruff check app` (0 lỗi), `mypy app` (0 lỗi trên 53 files).
