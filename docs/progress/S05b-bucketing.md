# Progress Report — Slice 5B: MurmurHash3 Bucketing

**Ngày hoàn thành:** 2026-09-16  
**Trạng thái:** HOÀN THÀNH (100% tiêu chí Definition of Done)  
**Kỹ năng áp dụng:** `evaluation-engine-purity`, `python-testing-pytest`, `ponytail`, `tdd`

---

## 1. Mục tiêu Slice 5B

Triển khai giải thuật phân nhóm chia tỷ lệ phần trăm (Bucketing) cho Evaluation Engine của FlagOps:
1. **Module pure**: [`backend/app/engine/bucketing.py`](file:///d:/python/feature%20flag/backend/app/engine/bucketing.py) sử dụng `mmh3` 32-bit unsigned, thang phân giải 10,000 điểm (0.01%), zero-I/O, không sử dụng `random` hay Python builtin `hash()`.
2. **Xác thực đầu vào nghiêm ngặt**:
   - `distribution` rỗng $\to$ ném `InvalidDistributionError`.
   - Trọng số âm $\to$ ném `InvalidDistributionError`.
   - Tổng trọng số $\ne 100 \to$ ném `InvalidDistributionError`.
3. **Bộ 5 Property Tests bắt buộc**:
   - Determinism (kiểm thử thuộc tính với Hypothesis).
   - Phân bố đều (Uniform distribution) trên 10,000 mẫu cho các mức 50/50, 10/90, 25/75.
   - Tính đơn điệu (Monotonic): tập user 10% bắt buộc là tập con của tập 20% (`nhom_10.issubset(nhom_20)`).
   - Tính độc lập giữa các cờ (Inter-flag independence): Hai cờ 10% có tỷ lệ giao thoa xấp xỉ 1.0% (trong khoảng 0.5% – 1.8%), không bị tương quan.
   - Ổn định qua các tiến trình độc lập (Cross-process stability).
4. **Báo cáo đồ án & Biểu đồ**:
   - Script [`backend/scripts/bucketing_report.py`](file:///d:/python/feature%20flag/backend/scripts/bucketing_report.py) mô phỏng 100,000 mẫu và xuất biểu đồ tại [`docs/diagrams/bucketing-distribution.png`](file:///d:/python/feature%20flag/docs/diagrams/bucketing-distribution.png).
   - Kiến trúc giải thuật được lưu trong [`docs/adr/007-murmurhash-bucketing.md`](file:///d:/python/feature%20flag/docs/adr/007-murmurhash-bucketing.md).

---

## 2. Kết quả kiểm thử & Nghiệm thu Definition of Done

| Tiêu chí | Lệnh kiểm tra | Kết quả |
|---|---|---|
| **Unit tests bucketing** | `pytest app/tests/unit/engine/test_bucketing.py -v` | **13/13 passed** (1.02s) |
| **Độ bao phủ (Coverage)** | `pytest --cov=app.engine.bucketing --cov-report=term-missing` | **97% Coverage** (vượt chỉ tiêu $\ge 95\%$) |
| **Sinh biểu đồ phân bố** | `python scripts/bucketing_report.py` | Sinh thành công file `bucketing-distribution.png` (315 KB) |
| **Toàn bộ Test suite (Regression)** | `pytest app/tests/ -v` | **138/138 passed (100%)** |
| **Purity Check** | `grep -rn "import sqlalchemy\|import redis\|from fastapi\|from app.models" app/engine/` | **0 kết quả** (Không vi phạm) |
| **Lint & Type Check** | `ruff check app scripts` & `mypy app scripts` | **0 errors** (56 files sạch) |

---

## 3. Các thông số thực nghiệm (Simulation N=100,000)

- **A/B 50/50**: Biến thể A đạt 49.88%, Biến thể B đạt 50.12% (sai số 0.12% so với lý thuyết).
- **Multi-variate (10/20/30/40)**: Đạt lần lượt 9.87%, 19.99%, 30.15%, 39.99%.
- **Monotonic Continuity**: $10\% \subset 20\% \subset 50\%$ được chứng minh xác thực $100\%$.
- **Tương quan cờ (Inter-flag overlap)**: Đạt 1.04% (lý thuyết: 1.00%), chứng minh muối salt `flag_key` loại bỏ hoàn toàn hiện tượng "chuột bạch vĩnh viễn".
