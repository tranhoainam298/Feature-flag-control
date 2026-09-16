---
name: postgres-alembic-migrations
description: >
  Quy ước model SQLAlchemy và migration Alembic cho FlagOps.
  Nạp khi thêm/sửa bảng hoặc tạo migration mới.
---

# Quy ước Model SQLAlchemy & Migration Alembic

## 1. Primary Key — UUID

Mọi bảng dùng UUID làm PK (trừ `audit_log` dùng BIGSERIAL, `evaluation_event` dùng BIGSERIAL).

### Ví dụ ĐÚNG:
```python
import uuid
from sqlalchemy import Column, text
from sqlalchemy.dialects.postgresql import UUID

class Flag(Base):
    __tablename__ = "flag"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                server_default=text("gen_random_uuid()"))
```

### Ví dụ SAI:
```python
# ❌ Auto-increment integer PK
class Flag(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)  # CẤM — dùng UUID
```

## 2. Timestamp — TIMESTAMPTZ

Tất cả cột thời gian dùng `TIMESTAMP WITH TIME ZONE`, KHÔNG dùng `TIMESTAMP` không timezone.

```python
from sqlalchemy import Column, func
from sqlalchemy.dialects.postgresql import TIMESTAMP

created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
```

## 3. JSONB cho dữ liệu linh hoạt

Các cột sau PHẢI dùng `JSONB`, KHÔNG dùng TEXT + json.loads:
- `segment.conditions` — cây điều kiện AND/OR
- `targeting_rule.distribution` — `[{"variation_id": "...", "weight": 30}]`
- `targeting_rule.conditions` — điều kiện viết trực tiếp
- `config_release.snapshot` — ảnh chụp toàn bộ key-value
- `change_request.payload` — tập thay đổi chờ áp dụng
- `audit_log.before`, `audit_log.after` — giá trị trước/sau

```python
from sqlalchemy.dialects.postgresql import JSONB
conditions = Column(JSONB, nullable=True)
```

## 4. Enum — Native PostgreSQL Enum

KHÔNG dùng String cho enum. Dùng native PG enum kết hợp Python enum.

### Ví dụ ĐÚNG:
```python
import enum
from sqlalchemy import Column, Enum

class FlagType(str, enum.Enum):
    BOOLEAN = "BOOLEAN"
    STRING = "STRING"
    NUMBER = "NUMBER"
    JSON = "JSON"

class Flag(Base):
    type = Column(Enum(FlagType, name="flag_type", create_type=True), nullable=False)
```

### Ví dụ SAI:
```python
# ❌ String thay cho enum
class Flag(Base):
    type = Column(String(20))  # CẤM — không validate, typo không bắt được
```

## 5. Mọi bảng PHẢI có created_at / updated_at

Tạo mixin để tái sử dụng:

```python
class TimestampMixin:
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
```

## 6. Soft delete bằng archived_at

Không xóa cứng dữ liệu quan trọng. Dùng `archived_at` (TIMESTAMPTZ, nullable).

```python
archived_at = Column(TIMESTAMP(timezone=True), nullable=True)
```

Query mặc định phải lọc `WHERE archived_at IS NULL`. Index partial:
```sql
CREATE INDEX idx_flag_project_key ON flag(project_id, key) WHERE archived_at IS NULL;
```

## 7. Index bắt buộc (từ Phần F.4 kế hoạch)

Migration PHẢI tạo đủ các index sau:

```sql
-- Flag environment setting: tra cứu theo env + flag
CREATE INDEX idx_fes_env_flag ON flag_environment_setting(environment_id, flag_id);

-- Targeting rule: sắp xếp theo priority trong setting
CREATE INDEX idx_rule_fes_priority ON targeting_rule(flag_environment_setting_id, priority);

-- Flag: tra cứu theo project + key, chỉ flag chưa archive
CREATE INDEX idx_flag_project_key ON flag(project_id, key) WHERE archived_at IS NULL;

-- Audit log: BRIN index theo thời gian (bảng append-only)
CREATE INDEX idx_audit_created_brin ON audit_log USING BRIN(created_at);

-- Audit log: tra cứu theo entity
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);

-- API key: tra cứu theo hash, chỉ key chưa thu hồi
CREATE INDEX idx_apikey_hash ON api_key(key_hash) WHERE revoked_at IS NULL;

-- Segment: GIN index cho JSONB conditions
CREATE INDEX idx_segment_cond_gin ON segment USING GIN(conditions);
```

### Ví dụ SAI:
```python
# ❌ Quên tạo index → query chậm khi có nhiều dữ liệu
# ❌ Dùng btree cho JSONB conditions thay vì GIN
```

## 8. Migration — một thay đổi = một migration

### Quy tắc bắt buộc:
- Mỗi thay đổi model → tạo migration MỚI: `alembic revision --autogenerate -m "mô tả"`
- **KHÔNG SỬA migration đã commit** lên Git
- Luôn viết CẢ `upgrade()` VÀ `downgrade()`
- Message migration phải mô tả rõ: `"add_flag_table"`, `"add_gin_index_segment_conditions"`

### Ví dụ ĐÚNG:
```python
def upgrade() -> None:
    op.create_table(
        "flag",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("type", sa.Enum("BOOLEAN", "STRING", "NUMBER", "JSON", name="flag_type"), nullable=False),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "key", name="uq_flag_project_key"),
    )

def downgrade() -> None:
    op.drop_table("flag")
```

### Ví dụ SAI:
```python
# ❌ Chỉ có upgrade, không có downgrade
def upgrade() -> None:
    op.add_column("flag", sa.Column("tags", postgresql.ARRAY(sa.Text)))

def downgrade() -> None:
    pass  # CẤM — phải viết op.drop_column(...)
```

## 9. Danh sách Enum cần tạo (từ kế hoạch)

| Enum name | Giá trị |
|-----------|---------|
| `member_role` | OWNER, ADMIN, DEVELOPER, VIEWER |
| `flag_type` | BOOLEAN, STRING, NUMBER, JSON |
| `toggle_kind` | RELEASE, EXPERIMENT, OPS, PERMISSION |
| `api_key_scope` | SERVER, CLIENT |
| `config_value_type` | STRING, INT, FLOAT, BOOL, JSON |
| `config_format` | PROPERTIES, JSON, YAML |
| `change_request_status` | DRAFT, PENDING, APPROVED, REJECTED, APPLIED, CANCELLED |

## 10. Bảng evaluation_event — phân vùng

Bảng này sẽ rất lớn, PHẢI phân vùng theo RANGE(created_at):

```sql
CREATE TABLE evaluation_event (
    id BIGSERIAL,
    environment_id UUID NOT NULL,
    flag_id UUID NOT NULL,
    variation_id UUID NOT NULL,
    reason VARCHAR(30) NOT NULL,
    context_key_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);
```

## 11. Checklist tự kiểm tra

- [ ] PK dùng UUID (trừ audit_log, evaluation_event)
- [ ] Mọi cột thời gian dùng TIMESTAMPTZ
- [ ] Dữ liệu linh hoạt dùng JSONB, không TEXT
- [ ] Enum dùng native PG enum, không String
- [ ] Mọi bảng có created_at, updated_at
- [ ] Soft delete bằng archived_at
- [ ] Đủ 7 index bắt buộc từ F.4
- [ ] Migration có cả upgrade và downgrade
- [ ] Không sửa migration đã commit
- [ ] Message migration mô tả rõ ràng
