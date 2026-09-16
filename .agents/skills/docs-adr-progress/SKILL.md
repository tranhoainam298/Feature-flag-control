---
name: docs-adr-progress
description: >
  Format tài liệu FlagOps — ADR và file tiến độ sau mỗi slice.
  Nạp khi kết thúc một slice hoặc khi cần ghi Architecture Decision Record.
---

# Tài liệu ADR & Tiến độ FlagOps

## 1. Architecture Decision Record (ADR)

### Vị trí: `docs/adr/NNN-ten-quyet-dinh.md`

ADR là tài liệu ghi lại quyết định kiến trúc QUAN TRỌNG. Hội đồng đánh giá rất cao nhóm nào
có ADR — vì nó thể hiện tư duy kỹ thuật có hệ thống, không phải "code trước nghĩ sau".

### Template ADR:

```markdown
# ADR-NNN: Tiêu đề quyết định

## Trạng thái
Accepted | Superseded by ADR-XXX | Deprecated

## Ngày
YYYY-MM-DD

## Ngữ cảnh (Context)
Mô tả vấn đề cần giải quyết, ràng buộc kỹ thuật, yêu cầu nghiệp vụ
liên quan. Viết đủ chi tiết để người đọc hiểu TẠI SAO phải ra quyết định này.

## Quyết định (Decision)
Mô tả rõ ràng quyết định đã chọn. Viết dạng câu khẳng định:
"Chúng tôi sẽ dùng..." hoặc "Hệ thống sẽ...".

## Phương án thay thế (Alternatives Considered)
Liệt kê ít nhất 2 phương án khác đã xem xét, kèm ưu/nhược điểm
và lý do KHÔNG chọn.

| Phương án | Ưu điểm | Nhược điểm | Lý do không chọn |
|-----------|---------|------------|-------------------|
| ... | ... | ... | ... |

## Hệ quả (Consequences)
### Tích cực
- ...

### Tiêu cực (trade-off)
- ...

### Rủi ro
- ...
```

### Ví dụ ĐÚNG:
```markdown
# ADR-001: Tuân thủ chuẩn OpenFeature

## Trạng thái
Accepted

## Ngày
2026-09-16

## Ngữ cảnh
Hệ thống cần expose API đánh giá flag cho SDK. Có hai hướng:
tự thiết kế API hoặc tuân thủ chuẩn OpenFeature (CNCF).

## Quyết định
Tuân thủ chuẩn OpenFeature cho API đánh giá. Reason code, error code,
và EvaluationContext theo spec OpenFeature.

## Phương án thay thế
| Phương án | Ưu điểm | Nhược điểm | Lý do không chọn |
|-----------|---------|------------|-------------------|
| Tự thiết kế API | Linh hoạt hoàn toàn | Phải viết SDK từ đầu, không có chuẩn đối chiếu | Tốn thời gian, khó chứng minh tính đúng đắn |
| Fork SDK có sẵn | Nhanh | Khó tùy chỉnh, vướng license | Không phù hợp đồ án |

## Hệ quả
### Tích cực
- Dùng lại SDK OpenFeature có sẵn cho nhiều ngôn ngữ
- Chứng minh tính không khóa nhà cung cấp (vendor lock-in)
- Có bộ test tuân thủ chuẩn

### Tiêu cực
- Bị ràng buộc bởi spec, không tự do thêm field tùy ý
```

### Ví dụ SAI:
```markdown
# ❌ ADR quá sơ sài — không có giá trị
# ADR-001: Dùng FastAPI
Dùng FastAPI vì nhanh.
# → Thiếu context, thiếu alternatives, thiếu consequences
```

## 2. Danh sách 7 ADR bắt buộc

| ADR | Tiêu đề | Thời điểm viết |
|-----|---------|----------------|
| 001 | Tuân thủ chuẩn OpenFeature | Tuần 1 |
| 002 | Evaluation engine là pure function, không I/O | Tuần 1 |
| 003 | MurmurHash3 cho sticky bucketing thay vì SHA/MD5 | Tuần 1 |
| 004 | Tách đường quản trị (JWT) và đánh giá (API key) | Tuần 2 |
| 005 | Config release lưu snapshot toàn bộ thay vì diff | Tuần 8 |
| 006 | SSE thay vì WebSocket cho kênh đẩy realtime | Tuần 10 |
| 007 | Tính debt score cho flag lifecycle | Tuần 12 |

## 3. File tiến độ sau mỗi slice

### Vị trí: `docs/progress/SXX-ten-slice.md`

Sau khi hoàn thành mỗi slice, tạo file progress để theo dõi tiến độ.

### Template Progress:

```markdown
# S{XX}: Tên slice

## Ngày hoàn thành
YYYY-MM-DD

## Implemented
- Danh sách chức năng đã triển khai
- Endpoint nào đã hoạt động
- Model/migration nào đã tạo

## Tests
- Số test đã viết: X unit, Y integration
- Coverage đạt: Z%
- Lệnh chạy test: `pytest tests/unit/test_xxx.py`

## Coverage Report
| Module | Coverage |
|--------|----------|
| engine/ | 97% |
| services/ | 82% |
| Tổng | 78% |

## Known Issues
- [ ] Issue 1: mô tả vắn tắt
- [ ] Issue 2: mô tả vắn tắt

## Dependencies
- Slice này phụ thuộc: S{YY}
- Slice phụ thuộc slice này: S{ZZ}

## Next
- Slice tiếp theo: S{XX+1} — tên slice
- Ước lượng thời gian: N ngày
```

### Ví dụ ĐÚNG:
```markdown
# S10: Engine v1 — Boolean evaluation

## Ngày hoàn thành
2026-10-10

## Implemented
- `backend/app/engine/evaluator.py` — hàm evaluate() chính
- `backend/app/engine/matcher.py` — match conditions
- `backend/app/engine/types.py` — dataclass cho Ruleset, EvaluationResult
- Xử lý: FLAG_NOT_FOUND, DISABLED, DEFAULT

## Tests
- 25 unit test cho engine
- Coverage engine: 92%
- `pytest tests/unit/engine/ -v`

## Known Issues
- [ ] Chưa có targeting rules (S12-S13)
- [ ] Chưa có bucketing (S14)

## Next
- S11: API evaluate + cache Redis
```

## 4. Quy ước Conventional Commits

Mọi commit PHẢI theo format:

```
<type>(<scope>): <mô tả ngắn>

[body tùy chọn]

[footer tùy chọn]
```

### Type hợp lệ:
| Type | Khi nào |
|------|---------|
| `feat` | Tính năng mới |
| `fix` | Sửa bug |
| `docs` | Chỉ thay đổi tài liệu |
| `test` | Thêm/sửa test |
| `refactor` | Thay đổi code nhưng không thêm tính năng, không sửa bug |
| `chore` | Build, CI, dependencies |
| `style` | Format code, không đổi logic |
| `perf` | Cải thiện hiệu năng |

### Scope hợp lệ:
`engine`, `auth`, `flags`, `config`, `segments`, `eval`, `sdk`, `frontend`, `ci`, `db`, `docs`

### Ví dụ ĐÚNG:
```
feat(engine): implement sticky bucketing with MurmurHash3

Use mmh3.hash() with flag_key:rule_id:context_value
to ensure independent distribution across flags.

Refs: ADR-003
```

```
fix(eval): return 304 when ruleset_version unchanged

Previously always returned 200 with full payload.
Now checks If-None-Match header against ruleset_version.
```

### Ví dụ SAI:
```
# ❌ Không có type và scope
update code

# ❌ Quá chung chung
fix: fix bug

# ❌ Sai type
feat: fix login error   # Đây là fix, không phải feat
```

## 5. Git flow

```
main ← develop ← feature/FO-123-ten-tinh-nang
```

- `main`: luôn deploy được, chỉ merge từ `develop` khi xong sprint
- `develop`: nhánh tích hợp
- `feature/*`: mỗi tính năng/slice một nhánh

PR phải:
- Có ít nhất 1 reviewer
- CI xanh
- Không quá 500 dòng thay đổi (tách nếu lớn hơn)

## 6. Checklist tự kiểm tra

- [ ] ADR có đủ 4 phần: Context, Decision, Alternatives, Consequences
- [ ] ADR có ít nhất 2 phương án thay thế
- [ ] Progress file có đủ: Implemented, Tests, Coverage, Known Issues, Next
- [ ] Commit theo Conventional Commits format
- [ ] Commit message có scope phù hợp
- [ ] PR ≤ 500 dòng, có reviewer, CI xanh
- [ ] 7 ADR bắt buộc đã lên kế hoạch viết
