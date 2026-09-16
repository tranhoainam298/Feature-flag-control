---
name: security-hardening
description: >
  Quy tắc bảo mật FlagOps — API key, RBAC, secret, rate limit, OWASP.
  Nạp khi làm auth, api key, config secret, hoặc khi review bảo mật.
---

# Quy tắc Bảo mật FlagOps

## 1. API Key — Chỉ lưu hash

Khi tạo API key:
1. Sinh random key: `fo_srv_` + 32 byte random (base62)
2. Tính `key_hash = SHA-256(raw_key)`
3. Lưu `key_hash` + `key_prefix` (12 ký tự đầu) vào database
4. Trả `raw_key` cho client **ĐÚNG 1 LẦN** trong response tạo key
5. KHÔNG BAO GIỜ lưu raw_key vào database

### Ví dụ ĐÚNG:
```python
import secrets
import hashlib

def create_api_key(scope: ApiKeyScope) -> tuple[str, str, str]:
    """Trả về (raw_key, key_hash, key_prefix)."""
    prefix = "fo_srv_" if scope == ApiKeyScope.SERVER else "fo_cli_"
    random_part = secrets.token_urlsafe(32)
    raw_key = f"{prefix}{random_part}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]
    return raw_key, key_hash, key_prefix

# Khi xác thực: hash key từ request, tìm trong DB
async def verify_api_key(x_flagops_key: str = Header(...)):
    key_hash = hashlib.sha256(x_flagops_key.encode()).hexdigest()
    api_key = await repo.find_by_hash(key_hash)  # Tìm bằng hash
    if not api_key or api_key.revoked_at is not None:
        raise UnauthorizedError()
    if api_key.expires_at and api_key.expires_at < utcnow():
        raise UnauthorizedError()
    return api_key
```

### Ví dụ SAI:
```python
# ❌ Lưu raw key
api_key = ApiKey(raw_key="fo_srv_abc123...")  # CẤM — lộ key nếu DB bị xâm nhập

# ❌ Trả raw key khi GET
@router.get("/api-keys/{id}")
async def get_key(id: UUID):
    return {"key": api_key.raw_key}  # CẤM — chỉ trả được lúc tạo
```

## 2. CLIENT Key — Giới hạn quyền

Key có scope `CLIENT` (dùng ở frontend/mobile) chỉ được thấy flag có `is_client_visible=true`.

```python
async def get_flags_for_client_key(env_id: UUID, key_scope: ApiKeyScope):
    query = select(Flag).where(Flag.environment_id == env_id)
    if key_scope == ApiKeyScope.CLIENT:
        query = query.where(Flag.is_client_visible == True)  # Lọc bắt buộc
    return await session.execute(query)
```

CLIENT key KHÔNG được trả về targeting rules (tránh lộ logic business).

## 3. Cross-org access → 404 (không 403)

Khi user org A cố truy cập resource của org B:
- Trả **404 Not Found** — giả như resource không tồn tại
- KHÔNG trả 403 Forbidden — sẽ lộ rằng resource tồn tại

### Ví dụ ĐÚNG:
```python
async def get_project(project_id: UUID, current_user: User):
    project = await repo.get(project_id)
    if not project or project.organization_id != current_user.organization_id:
        raise NotFoundError("project", str(project_id))  # 404, không 403
```

## 4. Password — Argon2id

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

KHÔNG dùng bcrypt (chậm nhưng kém chống GPU hơn Argon2id).
KHÔNG dùng SHA-256/MD5 cho password (quá nhanh → brute force dễ).

## 5. Config Secret — AES-256-GCM

Giá trị cấu hình đánh dấu `is_secret=true` phải mã hóa trước khi lưu.

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, base64

def encrypt_secret(plaintext: str, master_key: bytes) -> str:
    """Master key = 32 bytes từ env var CONFIG_MASTER_KEY."""
    nonce = os.urandom(12)
    ct = AESGCM(master_key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()

def decrypt_secret(ciphertext_b64: str, master_key: bytes) -> str:
    data = base64.b64decode(ciphertext_b64)
    nonce, ct = data[:12], data[12:]
    return AESGCM(master_key).decrypt(nonce, ct, None).decode()
```

**Master key:**
- Lấy từ biến môi trường `CONFIG_MASTER_KEY`
- KHÔNG BAO GIỜ commit vào Git
- KHÔNG hardcode trong code
- `.env.example` ghi placeholder: `CONFIG_MASTER_KEY=change-me-32-bytes-key-here!!!!`

**API trả secret:**
- Mặc định trả `"••••••"` (masked)
- Chỉ trả plaintext nếu user có role `ADMIN`+ VÀ request có `?reveal=true`
- Ghi audit log mỗi lần reveal

## 6. RBAC — Phân quyền theo vai trò

| Hành động | OWNER | ADMIN | DEVELOPER | VIEWER |
|-----------|-------|-------|-----------|--------|
| Quản lý thành viên | ✅ | ✅ | ❌ | ❌ |
| Tạo/xóa project | ✅ | ✅ | ❌ | ❌ |
| CRUD flag/segment | ✅ | ✅ | ✅ | ❌ |
| Bật/tắt flag | ✅ | ✅ | ✅ | ❌ |
| Xem flag/config | ✅ | ✅ | ✅ | ✅ |
| Reveal secret | ✅ | ✅ | ❌ | ❌ |
| Duyệt change request | ✅ | ✅ | ❌ | ❌ |

## 7. CẤM log thông tin nhạy cảm

```python
# ❌ CẤM log các giá trị sau dưới BẤT KỲ hình thức nào
logger.info(f"User password: {password}")          # CẤM
logger.debug(f"JWT token: {token}")                # CẤM
logger.info(f"API key: {api_key}")                 # CẤM
logger.info(f"Secret value: {config_value}")       # CẤM
logger.info(f"Master key: {master_key}")           # CẤM

# ✅ ĐÚNG — log thông tin không nhạy cảm
logger.info(f"User {user_id} logged in")
logger.info(f"API key prefix: {key_prefix}")       # Chỉ prefix
logger.info(f"Config key '{key}' updated")          # Chỉ tên key
```

## 8. Regex timeout — Chống ReDoS

Mọi regex do user nhập (toán tử `MATCHES_REGEX`) PHẢI có timeout:

```python
# Giới hạn 50ms cho mỗi regex evaluation
# Dùng google-re2 (không backtrack) hoặc regex module có timeout
import re

def safe_regex_match(pattern: str, value: str, timeout_ms: int = 50) -> bool:
    try:
        # Trong production, ưu tiên dùng google-re2
        return re.fullmatch(pattern, value) is not None
    except (re.error, TimeoutError):
        return False
```

## 9. Giới hạn độ sâu điều kiện

Cây điều kiện JSONB lồng tối đa **5 tầng**. Nếu vượt → trả 400 `CONDITION_TOO_DEEP`.
Tránh DoS bằng cách gửi JSON siêu sâu.

## 10. Rate limit

API đánh giá `/eval/v1/*`:
- Mặc định: 1000 req/phút/key
- Vượt ngưỡng → 429 `RATE_LIMITED`
- Dùng Redis sliding window hoặc token bucket

## 11. Checklist 10 ca test bảo mật BẮT BUỘC

| # | Ca test | Kỳ vọng |
|---|---------|---------|
| 1 | API key env `dev` gọi ruleset `prod` | 403 |
| 2 | CLIENT key lấy flag `is_client_visible=false` | Flag không xuất hiện |
| 3 | VIEWER gọi API sửa flag | 403 |
| 4 | User org A truy cập project org B | 404 (KHÔNG 403) |
| 5 | API key đã thu hồi (revoked) | 401 |
| 6 | 10.000 req/phút từ một key | 429 sau ngưỡng |
| 7 | Regex `(a+)+$` với chuỗi 1000 ký tự | Timeout, không treo |
| 8 | JSONB điều kiện lồng 50 tầng | 400 CONDITION_TOO_DEEP |
| 9 | SQL injection qua tham số lọc | Bị chặn (ORM tham số hóa) |
| 10 | XSS qua tên flag/mô tả | Escape đúng |

## 12. Checklist tự kiểm tra

- [ ] API key chỉ lưu hash + prefix, raw key trả 1 lần
- [ ] CLIENT key chỉ thấy flag `is_client_visible=true`
- [ ] Cross-org → 404, không 403
- [ ] Password dùng Argon2id
- [ ] Secret mã hóa AES-256-GCM, master key từ env
- [ ] Không log password/JWT/API key/secret
- [ ] Regex có timeout
- [ ] Depth limit = 5 cho cây điều kiện
- [ ] Rate limit trên eval API
- [ ] 10 ca test bảo mật đã viết và pass
