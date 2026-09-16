---
name: api-contract-rest
description: >
  Hợp đồng API của FlagOps — đường dẫn, mã lỗi, error envelope, ETag.
  Nạp khi tạo hoặc sửa endpoint.
---

# Hợp đồng API FlagOps

## 1. Hai đường API tách biệt

| Đường | Base path | Auth | Mục đích |
|-------|-----------|------|----------|
| Quản trị | `/api/v1/*` | `Authorization: Bearer <JWT>` | Dashboard, CRUD, admin |
| Đánh giá | `/eval/v1/*` | `X-FlagOps-Key: <api_key>` | SDK gọi, lưu lượng cao |

### Ví dụ ĐÚNG:
```python
# Endpoint quản trị — JWT
@admin_router.get("/api/v1/projects/{project_id}/flags")
async def list_flags(..., current_user: User = Depends(get_current_user)):
    ...

# Endpoint đánh giá — API Key
@eval_router.post("/eval/v1/flags/{flag_key}/evaluate")
async def evaluate_flag(..., api_key: ApiKey = Depends(verify_api_key)):
    ...
```

### Ví dụ SAI:
```python
# ❌ Đánh giá dùng JWT — SDK không nên giữ JWT
@router.post("/api/v1/evaluate")  # CẤM — eval phải ở /eval/v1/
async def evaluate(..., user: User = Depends(get_current_user)):  # CẤM — dùng API key
    ...
```

## 2. Error Envelope chuẩn

MỌI response lỗi PHẢI theo format này:

```json
{
  "error": {
    "code": "FLAG_NOT_FOUND",
    "message": "Flag 'checkout-v2' không tồn tại trong môi trường 'production'",
    "details": {}
  },
  "request_id": "01J8X..."
}
```

KHÔNG trả lỗi dạng khác. KHÔNG trả `{"detail": "Not found"}` (FastAPI default).

## 3. Bảng mã lỗi HTTP

| Status | Code | Khi nào dùng |
|--------|------|-------------|
| 400 | `INVALID_INPUT` | Request body sai schema, giá trị không hợp lệ |
| 400 | `CONDITION_TOO_DEEP` | Cây điều kiện lồng quá 5 tầng |
| 400 | `DISTRIBUTION_INVALID` | Tổng weight ≠ 100 |
| 401 | `UNAUTHORIZED` | Không có token/key, token hết hạn, key không tồn tại |
| 403 | `FORBIDDEN` | Có token nhưng không đủ quyền (VIEWER sửa flag) |
| 404 | `*_NOT_FOUND` | Resource không tồn tại HOẶC không thuộc org của user |
| 409 | `CONFLICT` | Flag key đã tồn tại, version conflict |
| 409 | `FLAG_KEY_IMMUTABLE` | Cố sửa flag key (bất biến) |
| 422 | `VALIDATION_ERROR` | Pydantic validation thất bại (tự động từ FastAPI) |
| 429 | `RATE_LIMITED` | Vượt ngưỡng rate limit |

**Quan trọng:** Khi org A truy cập resource của org B → trả **404**, KHÔNG trả 403.
Trả 403 sẽ lộ rằng resource TỒN TẠI, vi phạm bảo mật.

## 4. Danh sách endpoint chính

### Quản trị Auth:
```
POST   /api/v1/auth/register       → Đăng ký
POST   /api/v1/auth/login          → Đăng nhập (access + refresh token)
POST   /api/v1/auth/refresh        → Làm mới token
```

### Quản trị Resource:
```
GET    /api/v1/organizations/{org}/projects
POST   /api/v1/projects/{p}/environments
POST   /api/v1/environments/{e}/api-keys       → Trả khóa gốc ĐÚNG 1 LẦN
GET    /api/v1/projects/{p}/flags               → Lọc theo tag/trạng thái
POST   /api/v1/projects/{p}/flags               → Tạo flag + variations
PATCH  /api/v1/flags/{f}                         → Sửa metadata (KHÔNG cho sửa key)
PUT    /api/v1/flags/{f}/environments/{e}        → Bật/tắt, đổi default variation
PUT    /api/v1/flags/{f}/environments/{e}/rules  → Ghi đè TOÀN BỘ tập rule (atomic)
POST   /api/v1/flags/{f}/environments/{e}/simulate → Mô phỏng đánh giá
GET    /api/v1/projects/{p}/segments
GET    /api/v1/environments/{e}/namespaces
PUT    /api/v1/namespaces/{n}/items              → Sửa bản nháp cấu hình
POST   /api/v1/namespaces/{n}/releases           → Publish → tạo release mới
GET    /api/v1/namespaces/{n}/releases/{v1}/diff/{v2}  → So sánh hai release
POST   /api/v1/namespaces/{n}/releases/{v}/rollback
GET    /api/v1/environments/{e}/audit-logs       → Phân trang cursor
POST   /api/v1/environments/{e}/change-requests
POST   /api/v1/change-requests/{c}/approve
GET    /api/v1/projects/{p}/flag-health          → Báo cáo nợ kỹ thuật
```

### Đánh giá (đường nóng):
```
POST   /eval/v1/flags/{flag_key}/evaluate      → Đánh giá một flag
POST   /eval/v1/flags/evaluate-all              → Đánh giá tất cả
GET    /eval/v1/ruleset                          → Tải ruleset (ETag/304)
GET    /eval/v1/stream                           → SSE realtime
POST   /eval/v1/events                           → Batch evaluation events
GET    /eval/v1/config/{namespace}               → Tải config namespace
```

## 5. ETag cho ruleset

```
GET /eval/v1/ruleset
X-FlagOps-Key: fo_srv_...
If-None-Match: "142"
```

- `ETag` = `ruleset_version` của environment (BIGINT, tăng mỗi khi có thay đổi)
- Nếu version chưa đổi → trả `304 Not Modified` (body rỗng, tiết kiệm băng thông)
- Nếu đã đổi → trả `200` + ruleset mới + header `ETag: "143"`

### Ví dụ ĐÚNG:
```python
@eval_router.get("/eval/v1/ruleset")
async def get_ruleset(
    request: Request,
    api_key: ApiKey = Depends(verify_api_key),
    service: RulesetService = Depends(get_ruleset_service),
):
    env = api_key.environment
    client_version = request.headers.get("If-None-Match", "").strip('"')
    if client_version == str(env.ruleset_version):
        return Response(status_code=304)
    ruleset = await service.build_ruleset(env.id)
    return Response(
        content=ruleset.model_dump_json(),
        media_type="application/json",
        headers={"ETag": f'"{env.ruleset_version}"'},
    )
```

## 6. Phân trang — Cursor-based

KHÔNG dùng offset pagination (chậm với bảng lớn). Dùng cursor-based.

```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0wOS0xNiJ9",
    "has_more": true,
    "total": 142
  }
}
```

## 7. Response đánh giá

```json
{
  "flagKey": "checkout-v2",
  "value": true,
  "variant": "on",
  "reason": "TARGETING_MATCH",
  "flagMetadata": {
    "matchedRuleId": "rule-3",
    "matchedRuleDescription": "Premium users tại VN",
    "rulesetVersion": 142
  }
}
```

## 8. SSE Stream

```
GET /eval/v1/stream
Accept: text/event-stream
```

Events:
```
event: ruleset_updated
data: {"environmentId":"...","rulesetVersion":143}

event: heartbeat
data: {}
```

Heartbeat mỗi 25 giây để giữ kết nối qua proxy/load balancer.

## 9. Mọi endpoint PHẢI có

- `response_model` — Pydantic schema cho response
- `summary` — mô tả ngắn cho OpenAPI docs
- `status_code` — nếu khác 200 (vd: 201 cho POST tạo mới)

## 10. Checklist tự kiểm tra

- [ ] Endpoint quản trị ở `/api/v1/*`, đánh giá ở `/eval/v1/*`
- [ ] Auth đúng: JWT cho admin, X-FlagOps-Key cho eval
- [ ] Error trả đúng envelope `{error: {code, message, details}, request_id}`
- [ ] Không trả `{"detail": "..."}` (FastAPI default)
- [ ] Org A truy cập org B → 404 (không 403)
- [ ] ETag dùng `ruleset_version`, trả 304 khi chưa đổi
- [ ] Phân trang dùng cursor, không offset
- [ ] Mọi endpoint có `response_model` và `summary`
- [ ] POST tạo mới trả 201, không 200
