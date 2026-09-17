# FlagOps — Tài liệu Kiến trúc Hệ thống (Architecture Design Document)

Tài liệu này mô tả chi tiết kiến trúc phần mềm của **FlagOps** theo mô hình **C4 Model** (Context, Container, Component), các nguyên tắc kiến trúc bất biến và các quyết định thiết kế then chốt.

---

## 1. Bối cảnh Hệ thống (System Context - C4 Level 1)

Sơ đồ ngữ cảnh thể hiện ranh giới của FlagOps với các tác nhân người dùng và hệ thống bên ngoài:

```mermaid
graph TD
    PM["Product Manager<br/>(Quản lý phát hành, A/B testing)"]
    DEV["Software Engineer<br/>(Tích hợp SDK, khai báo cờ)"]
    SRE["SRE / DevOps Engineer<br/>(Vận hành, Kill switch, Change Request)"]
    AUDIT["Compliance Auditor<br/>(Kiểm toán, Tra cứu Audit log)"]

    subgraph Boundaries ["Ranh giới Doanh nghiệp"]
        FLAGOPS["<b>FlagOps Platform</b><br/>(Hệ thống Quản trị Feature Flag & Cấu hình)"]
        CLIENT_APPS["<b>Ứng dụng Nghiệp vụ</b><br/>(Web, Microservices, Mobile Backend)"]
    end

    EXT_MONITORING["Hệ thống Quan sát<br/>(Prometheus / Grafana / OTel)"]

    PM -->|"Quản trị Flag, % Rollout"| FLAGOPS
    DEV -->|"Định cấu hình, Rule builder"| FLAGOPS
    SRE -->|"Phê duyệt Change Request, Khóa khẩn cấp"| FLAGOPS
    AUDIT -->|"Tra cứu lịch sử kiểm toán"| FLAGOPS

    CLIENT_APPS -->|"Tải ruleset (ETag/304), Nghe sự kiện SSE"| FLAGOPS
    CLIENT_APPS -->|"Đánh giá Flag (In-process / Remote API)"| FLAGOPS

    FLAGOPS -->|"Xuất độ đo Prometheus (Metrics)"| EXT_MONITORING
```

### Các hệ thống tương tác:
- **Ứng dụng nghiệp vụ (Client Applications)**: Sử dụng FlagOps Python SDK hoặc JavaScript SDK để đánh giá cờ tính năng và lấy cấu hình dịch vụ.
- **Hệ thống giám sát (Observability)**: Thu thập các độ đo hiệu năng Prometheus từ FlagOps Core (`/metrics`).

---

## 2. Kiến trúc Container (Container Architecture - C4 Level 2)

Sơ đồ container mô tả các đơn vị thực thi độc lập (tiến trình, dịch vụ, kho lưu trữ dữ liệu) tạo nên nền tảng FlagOps:

```mermaid
graph TB
    subgraph ClientTier ["Tầng Trình duyệt & Người dùng"]
        SPA["<b>FlagOps Web Dashboard</b><br/>React 18 + TypeScript + Vite<br/>Tailwind CSS & Lucide Icons"]
    end

    subgraph AppTier ["Tầng Ứng dụng Khách"]
        APP["<b>Dịch vụ Nghiệp vụ</b><br/>FastAPI / Django / Node.js"]
        SDK["<b>FlagOps SDK</b><br/>Python / JavaScript<br/>(In-memory Cache + SSE Subscriber)"]
        APP --> SDK
    end

    subgraph CoreTier ["Tầng Dịch vụ Lõi FlagOps"]
        API["<b>FlagOps Core API</b><br/>FastAPI + Python 3.12 (Uvicorn)<br/>- Admin API (/api/v1)<br/>- Eval API (/eval/v1)"]
        SSE_HUB["<b>SSE Realtime Hub</b><br/>Asynchronous Event Streamer<br/>(/eval/v1/stream)"]
        SCHEDULER["<b>Background Scheduler</b><br/>APScheduler 3.x<br/>(Scheduled Changes & Stale Sweep)"]
    end

    subgraph DataTier ["Tầng Lưu trữ & Bộ đệm"]
        PG[("<b>PostgreSQL 16</b><br/>Nguồn sự thật chính<br/>- JSONB Rules & Release Snapshots<br/>- Partitioned Evaluation Events")]
        REDIS[("<b>Redis 7</b><br/>- Distributed Ruleset Cache<br/>- Pub/Sub Invalidation Bus<br/>- Sliding Window Rate Limiting")]
    end

    SPA -->|"HTTPS / REST API (JWT Bearer)"| API
    SDK -->|"HTTP Polling (X-FlagOps-Key, ETag)"| API
    SDK -->|"Server-Sent Events (SSE Stream)"| SSE_HUB

    API -->|"SQLAlchemy 2.0 Async (asyncpg)"| PG
    API -->|"Cache Read/Write, Invalidation Pub"| REDIS
    SSE_HUB -->|"Subscribe 'flagops:invalidation'"| REDIS
    SCHEDULER -->|"Query & Apply Scheduled Changes"| PG
    SCHEDULER -->|"Publish Invalidation Event"| REDIS
```

---

## 3. Kiến trúc Thành phần Backend (Component Architecture - C4 Level 3)

Mô tả chi tiết cấu trúc phân tầng nghiêm ngặt bên trong `backend/app/`:

```mermaid
graph TD
    subgraph RoutingLayer ["Tầng Router (API Handlers)"]
        ADMIN_R["Admin Routers (/api/v1/*)<br/>auth, flags, config, change_requests, audit"]
        EVAL_R["Eval Routers (/eval/v1/*)<br/>flags, ruleset, stream, events"]
    end

    subgraph MiddlewareLayer ["Tầng Bảo vệ & Giám sát (Middleware & Deps)"]
        AUTH_DEP["Auth & RBAC Guards<br/>(JWT, API Key Scopes, Tenancy)"]
        RATE_LIMIT["Rate Limiter (Redis)"]
        AUDIT_MW["Audit Middleware"]
    end

    subgraph ServiceLayer ["Tầng Dịch vụ Nghiệp vụ (Business Logic)"]
        AUTH_SVC["AuthService"]
        FLAG_SVC["FlagService"]
        CONFIG_SVC["ConfigService"]
        CR_SVC["ChangeRequestService"]
        EVAL_SVC["EvaluationService"]
        DEBT_SVC["FlagDebtService"]
        CACHE_SVC["RulesetCacheService"]
    end

    subgraph EngineLayer ["Tầng Evaluation Engine (Pure - Không I/O)"]
        EVALUATOR["Evaluator (evaluate)"]
        MATCHER["Matcher (match_conditions)"]
        BUCKETING["Bucketing (MurmurHash3)"]
        OPERATORS["Operators (14 so sánh)"]
    end

    subgraph DataAccessLayer ["Tầng Truy xuất Dữ liệu (ORM & Repositories)"]
        MODELS["SQLAlchemy 2.0 Models<br/>(User, Flag, Environment, ConfigRelease...)"]
        DB_SESSION["Async Database Session (asyncpg)"]
    end

    ADMIN_R --> AUTH_DEP
    ADMIN_R --> AUDIT_MW
    EVAL_R --> AUTH_DEP
    EVAL_R --> RATE_LIMIT

    AUTH_DEP --> AUTH_SVC
    ADMIN_R --> FLAG_SVC
    ADMIN_R --> CONFIG_SVC
    ADMIN_R --> CR_SVC
    ADMIN_R --> DEBT_SVC
    EVAL_R --> EVAL_SVC

    EVAL_SVC --> CACHE_SVC
    EVAL_SVC --> EVALUATOR
    CR_SVC --> EVAL_SVC

    EVALUATOR --> MATCHER
    EVALUATOR --> BUCKETING
    MATCHER --> OPERATORS

    FLAG_SVC --> MODELS
    CONFIG_SVC --> MODELS
    CR_SVC --> MODELS
    AUTH_SVC --> MODELS
    MODELS --> DB_SESSION
```

---

## 4. Các Quyết định Kiến trúc Then chốt (Architectural Decisions)

### 4.1. Quy tắc Phụ thuộc Một chiều Tuyệt đối
Hệ thống tuân thủ mô hình phân tầng chặt chẽ:
$$\text{API} \longrightarrow \text{Services} \longrightarrow \text{Repositories / Models} \longrightarrow \text{Database}$$
- **Quy tắc 1**: Tầng Router (API) chỉ gọi xuống Services; không bao giờ truy vấn trực tiếp CSDL.
- **Quy tắc 2**: Tầng Evaluation Engine (`app/engine/`) là trung tâm tính toán thuần túy. Engine **tuyệt đối không import** bất kỳ module nào thuộc tầng trên (không import `models`, `services`, `api`, `sqlalchemy`, `redis`, `httpx`).

### 4.2. Tính Thuần khiết của Engine Đánh giá (Evaluation Engine Purity)
- Engine nhận đầu vào là cấu trúc dữ liệu thuần (`Ruleset` và `EvaluationContext`) và trả về `EvaluationResult`.
- Không thực hiện bất kỳ thao tác I/O nào (không đọc đĩa, không gọi mạng, không đọc đồng hồ hệ thống `datetime.now()`, không dùng số ngẫu nhiên `random`).
- **Lợi ích kiến trúc**:
  1. Engine có thể nhúng trực tiếp vào SDK Python (In-process evaluation) mà không cần viết lại logic, đạt tính tương đương 100% (Bit-for-bit parity).
  2. Dễ dàng kiểm thử tự động với Property-based Testing (`hypothesis`).
  3. Cực kỳ nhanh ($< 15\ \mu\text{s}$ cho mỗi lần evaluate).

### 4.3. Phân tách Hai Đường Đọc/Ghi (Read/Write Separation)
- **Đường Quản trị (Admin Path - `/api/v1/*`)**:
  - Đối tượng: Người dùng Web Dashboard.
  - Lưu lượng: Thấp đến trung bình ($\sim 10 - 100\ \text{req/s}$).
  - Xác thực: JWT Bearer Token, kiểm tra quyền RBAC 4 vai trò.
  - Thao tác: Ghi dữ liệu vào PostgreSQL, kích hoạt event lên Redis.
- **Đường Đánh giá (Evaluation Path - `/eval/v1/*`)**:
  - Đối tượng: Hàng nghìn instance SDK của ứng dụng khách.
  - Lưu lượng: Cực lớn ($\ge 10.000\ \text{req/s}$).
  - Xác thực: Khóa `X-FlagOps-Key` (băm SHA-256 đối chiếu bộ nhớ đệm).
  - Thao tác: Đọc thuần túy từ Redis Cache hoặc In-memory Ruleset.

### 4.4. Cơ chế Đẩy Thời gian thực & Invalidation Phân tán
1. Quản trị viên thay đổi trạng thái flag hoặc cấu hình trên Dashboard.
2. Core API cập nhật bản ghi trong PostgreSQL và tăng `ruleset_version` của môi trường.
3. Core API xóa cache Redis cục bộ và gửi thông điệp `ruleset_invalidated` lên kênh `flagops:invalidation` của Redis Pub/Sub.
4. Các instance của SSE Hub (có thể scale ngang) nhận thông điệp và truyền phát sự kiện `ruleset_updated` kèm số version mới tới tất cả các kết nối SSE đang mở của SDK.
5. SDK nhận được sự kiện, ngay lập tức gửi yêu cầu `GET /eval/v1/ruleset` kèm header `If-None-Match: "<old_version>"`.
6. Server trả về ruleset mới, SDK cập nhật bộ nhớ RAM nguyên tử. Toàn bộ tiến trình diễn ra trong $< 2.0\ \text{giây}$.

---

## 5. Kiến trúc Bảo mật & Độ tin cậy (Security & Resilience)

| Vấn đề kiến trúc | Giải pháp thiết kế trong FlagOps |
|---|---|
| **Bảo vệ ranh giới tổ chức (Multi-tenancy)** | Xác thực `organization_id` ở tầng dependency. Truy cập trái phép trả về mã `404 Not Found` thay vì `403` để chống Information Disclosure. |
| **Bảo mật bí mật cấu hình (Secret Management)** | Mã hóa khóa đối xứng AES-256-GCM với Initialization Vector (IV) 12 bytes ngẫu nhiên trước khi lưu trường `value` của bảng `config_item`. |
| **Chống treo hệ thống bởi Regex (ReDoS)** | Khống chế thời gian chạy của `regex.match` với timeout 200ms bằng luồng bảo vệ độc lập; từ chối các pattern độc hại. |
| **Ngăn chặn cạn kiệt ngăn xếp (Stack Overflow)** | Giới hạn độ sâu tối đa của cây điều kiện JSONB là 10 tầng; kiểm tra đệ quy trước khi nạp vào engine. |
| **Độ tin cậy SDK (Fail-safe Fallback)** | SDK bọc toàn bộ khối xử lý mạng bằng khối `try-except Exception`, luôn trả về giá trị mặc định được định nghĩa trước khi có sự cố. |
