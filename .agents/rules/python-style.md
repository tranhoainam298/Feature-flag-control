# Python Style — Quy ước viết code Python cho FlagOps

## Formatting & Linting
- **PEP 8** là tiêu chuẩn. Dùng `ruff` để lint và `black` để format.
- Line length: 100 ký tự (cấu hình trong `pyproject.toml`).
- Import order: stdlib → third-party → local (ruff tự sắp xếp).

## Type Hints — BẮT BUỘC
- Mọi hàm public PHẢI có type hint cho tham số và giá trị trả về.
- Dùng `X | None` thay cho `Optional[X]` (Python 3.12).
- Dùng `list[X]`, `dict[K, V]` thay cho `List[X]`, `Dict[K, V]`.

```python
# ✅ ĐÚNG
async def get_flag(self, session: AsyncSession, flag_id: UUID) -> Flag | None:
    ...

# ❌ SAI — thiếu type hint
async def get_flag(self, session, flag_id):
    ...
```

## Exception Handling
- **CẤM** dùng bare `except:` hoặc `except Exception: pass`.
- Luôn log hoặc re-raise exception.
- Chỉ bắt exception cụ thể mà bạn biết cách xử lý.

```python
# ❌ CẤM
try:
    ...
except Exception:
    pass

# ✅ ĐÚNG
try:
    ...
except ValueError as e:
    logger.warning(f"Invalid value: {e}")
    raise
```

## Docstring
- Module và class public: bắt buộc có docstring.
- Hàm phức tạp (> 10 dòng logic): bắt buộc có docstring.
