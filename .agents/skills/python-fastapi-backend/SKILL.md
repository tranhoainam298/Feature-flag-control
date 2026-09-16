---
name: python-fastapi-backend
description: >
  Quy ước viết backend FastAPI + SQLAlchemy 2.0 async + Pydantic v2 cho FlagOps.
  Nạp khi làm bất kỳ endpoint, service hay repository nào.
---

# Quy ước Backend FastAPI cho FlagOps

## 1. Async xuyên suốt

Toàn bộ backend dùng async/await. KHÔNG dùng hàm đồng bộ cho I/O.

### Ví dụ ĐÚNG:
```python
from sqlalchemy.ext.asyncio import AsyncSession

async def get_flag(self, session: AsyncSession, flag_id: UUID) -> Flag | None:
    result = await session.execute(select(Flag).where(Flag.id == flag_id))
    return result.scalar_one_or_none()
```

### Ví dụ SAI:
```python
# ❌ Hàm đồng bộ cho database
def get_flag(self, session: Session, flag_id: UUID) -> Flag | None:
    return session.query(Flag).get(flag_id)  # SQLAlchemy 1.x style, CẤM
```

## 2. Dependency Injection qua Depends

Mọi dependency (session, current_user, api_key, service) đều inject qua `Depends()`.

### Ví dụ ĐÚNG:
```python
from fastapi import APIRouter, Depends
from app.core.deps import get_db, get_current_user

router = APIRouter()

@router.get("/projects/{project_id}/flags", response_model=list[FlagRead])
async def list_flags(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    flag_service: FlagService = Depends(get_flag_service),
) -> list[FlagRead]:
    return await flag_service.list_flags(db, project_id, current_user)
```

### Ví dụ SAI:
```python
# ❌ Tạo session thủ công trong router
@router.get("/flags")
async def list_flags():
    async with async_session() as session:  # CẤM — dùng Depends
        ...
```

## 3. Response model bắt buộc

Mọi endpoint PHẢI có `response_model` và `summary` để OpenAPI tự sinh tài liệu.

```python
@router.post(
    "/projects/{project_id}/flags",
    response_model=FlagRead,
    status_code=201,
    summary="Tạo flag mới",
)
async def create_flag(...):
    ...
```

## 4. KHÔNG đặt business logic trong router

Router chỉ làm 3 việc:
1. Nhận request + validate input (Pydantic lo)
2. Gọi service
3. Trả response

### Ví dụ ĐÚNG:
```python
@router.put("/flags/{flag_id}/environments/{env_id}")
async def update_flag_setting(
    flag_id: UUID,
    env_id: UUID,
    payload: FlagSettingUpdate,
    service: FlagService = Depends(get_flag_service),
    db: AsyncSession = Depends(get_db),
) -> FlagSettingRead:
    return await service.update_setting(db, flag_id, env_id, payload)
```

### Ví dụ SAI:
```python
# ❌ Logic kiểm tra quyền, query DB, ghi audit NGAY trong router
@router.put("/flags/{flag_id}/environments/{env_id}")
async def update_flag_setting(...):
    flag = await db.execute(select(Flag).where(...))     # CẤM
    if not flag:
        raise HTTPException(404)
    flag.enabled = payload.enabled                        # CẤM
    await db.commit()                                     # CẤM
    await db.execute(insert(AuditLog).values(...))        # CẤM
```

## 5. Session — KHÔNG dùng global

### Ví dụ ĐÚNG:
```python
# backend/app/core/deps.py
from app.core.database import async_session_factory

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### Ví dụ SAI:
```python
# ❌ Session global dùng chung giữa các request
db = AsyncSession(engine)  # CẤM — race condition, leak connection
```

## 6. Chống N+1 query

Mọi relationship cần eager load PHẢI dùng `selectinload` hoặc `joinedload`.

### Ví dụ ĐÚNG:
```python
stmt = (
    select(Flag)
    .where(Flag.project_id == project_id, Flag.archived_at.is_(None))
    .options(selectinload(Flag.variations))
    .order_by(Flag.created_at.desc())
)
```

### Ví dụ SAI:
```python
# ❌ Lazy load → N+1 khi truy cập flag.variations trong vòng lặp
flags = await session.execute(select(Flag))
for flag in flags.scalars():
    print(flag.variations)  # Mỗi lần lặp = 1 query thêm → N+1
```

## 7. Pydantic v2 model_config

Dùng Pydantic v2 style, KHÔNG dùng class Config (v1 style).

### Ví dụ ĐÚNG:
```python
from pydantic import BaseModel, ConfigDict

class FlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, strict=True)

    id: UUID
    key: str
    name: str
    type: FlagType
    is_client_visible: bool
    created_at: datetime
```

### Ví dụ SAI:
```python
# ❌ Pydantic v1 style
class FlagRead(BaseModel):
    class Config:        # CẤM — dùng model_config = ConfigDict(...)
        orm_mode = True  # CẤM — đổi thành from_attributes=True
```

## 8. Exception chuẩn

Dùng custom exception + exception handler, KHÔNG raise HTTPException trực tiếp trong service.

### Ví dụ ĐÚNG:
```python
# backend/app/core/exceptions.py
class FlagOpsError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class NotFoundError(FlagOpsError):
    def __init__(self, entity: str, identifier: str):
        super().__init__(
            code=f"{entity.upper()}_NOT_FOUND",
            message=f"{entity} '{identifier}' không tồn tại",
            status_code=404,
        )

# backend/app/core/error_handler.py
@app.exception_handler(FlagOpsError)
async def flagops_error_handler(request: Request, exc: FlagOpsError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": exc.code, "message": exc.message, "details": exc.details},
            "request_id": request.state.request_id,
        },
    )
```

### Ví dụ SAI:
```python
# ❌ HTTPException trong service layer
from fastapi import HTTPException

class FlagService:
    async def get_flag(self, ...):
        if not flag:
            raise HTTPException(404, detail="Not found")  # CẤM — service không biết HTTP
```

## 9. Error envelope chuẩn

Mọi response lỗi đều theo format:
```json
{
  "error": {
    "code": "FLAG_NOT_FOUND",
    "message": "Flag 'checkout-v2' không tồn tại",
    "details": {}
  },
  "request_id": "01J8X..."
}
```

## 10. Checklist tự kiểm tra

- [ ] Tất cả endpoint có `response_model` và `summary`
- [ ] Tất cả hàm I/O là `async def`
- [ ] Không có business logic trong router
- [ ] Session inject qua `Depends(get_db)`, không global
- [ ] Mọi relationship cần thiết đã dùng `selectinload`/`joinedload`
- [ ] Pydantic schema dùng `model_config = ConfigDict(from_attributes=True)`
- [ ] Exception dùng custom class, không `raise HTTPException` trong service
- [ ] Mọi endpoint trả error đúng envelope chuẩn
