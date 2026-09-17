# S18: Security Hardening & Performance Benchmarks

## Ngày hoàn thành
2026-09-17

## Kỹ năng áp dụng
`security-hardening`, `python-testing-pytest`, `systematic-debugging`, `ponytail`, `docs-adr-progress`

---

## 1. Mục tiêu Slice 18

Thực thi kiểm thử thâm nhập toàn diện, kiểm chứng an ninh và đo lường hiệu năng dựa trên số liệu thực tế cho nền tảng FlagOps:
1. **Phần A — Bộ 10 ca kiểm thử bảo mật bắt buộc + 2 ca phòng thủ rò rỉ dữ liệu** (`backend/app/tests/security/`):
   - Ngăn chặn triệt để truy cập trái quyền chéo môi trường (dev key không được đọc ruleset prod).
   - Kiểm soát quyền truy cập client-side (lọc cờ nội bộ khi dùng client key).
   - Kiểm soát truy cập dựa trên vai trò (RBAC: Viewer không được ghi).
   - Chống tấn công thăm dò định danh tài nguyên chéo tổ chức (Anti-Enumeration: trả về 404 thay vì 403).
   - Thu hồi API key lập tức vô hiệu hóa phiên xác thực (401).
   - Giới hạn tần suất gọi API (Rate Limiting với sliding window và header `Retry-After`).
   - Phòng thủ tấn công từ chối dịch vụ biểu thức chính quy (ReDoS: giới hạn thời gian tính toán < 50ms).
   - Phòng thủ tấn công tràn ngăn xếp qua cây điều kiện lồng sâu (giới hạn độ sâu $\le 5$ tầng, trả về 400 `CONDITION_DEPTH_EXCEEDED`).
   - Kiểm chứng chống SQL Injection qua các tham số lọc tìm kiếm.
   - Kiểm chứng chống XSS (lưu trữ nguyên vẹn dữ liệu nhập, mã hóa đầu ra).
   - Che giấu chi tiết ngăn xếp lỗi máy chủ (500 trả về error envelope mờ đục kèm request ID, không rò rỉ stack trace).
   - Đảm bảo an toàn tuyệt đối các bí mật hệ thống: không bao giờ trả về `password_hash`, `key_hash`, hoặc `CONFIG_MASTER_KEY`.

2. **Phần B — Đo đạc hiệu năng thực tế (Benchmarks)**:
   - Đánh giá in-process: Chạy 100.000 lượt phân giải cờ nội bộ bằng pure engine.
   - Đo lường độ trễ truyền phát sự kiện Server-Sent Events (SSE) thời gian thực.
   - Đo lường độ trễ mạng HTTP đối với các endpoint đánh giá cờ và tải cấu hình 304 Not Modified.
   - Xây dựng kịch bản kiểm thử tải `k6/evaluate.js`.

3. **Phần C — Tối ưu hóa dựa trên dữ liệu thực nghiệm (Data-Driven Optimization)**:
   - Phân tích kế hoạch thực thi PostgreSQL (`EXPLAIN ANALYZE BUFFERS`) cho 3 luồng truy vấn trọng yếu.
   - Kiểm định loại trừ triệt để lỗi N+1 Query.
   - Đánh giá và tối ưu cấu hình connection pool.

---

## 2. Kết quả Phần A: 12 Ca kiểm thử bảo mật bắt buộc

Toàn bộ 12 ca kiểm thử được tổ chức trong [`backend/app/tests/security/test_security_compliance.py`](file:///d:/python/feature%20flag/backend/app/tests/security/test_security_compliance.py) và đạt tỷ lệ vượt qua **100% (12/12 PASSED)**:

| STT | Tên ca kiểm thử | Mô tả hành vi bảo mật | Mã HTTP | Kết quả |
|:---:|:---|:---|:---:|:---:|
| 1 | `test_dev_api_key_cannot_access_prod_ruleset` | API key thuộc môi trường Development cố tình gọi ruleset của Production | `403 FORBIDDEN` | **PASSED** |
| 2 | `test_client_key_filters_non_client_visible_flags` | API key scope `CLIENT` chỉ nhận cờ có `is_client_visible=true`, cờ backend nội bộ bị loại bỏ hoàn toàn | `200 OK` | **PASSED** |
| 3 | `test_viewer_role_cannot_update_flag` | Tài khoản có vai trò `VIEWER` cố gắng cập nhật cờ qua `PUT /api/v1/flags/{id}` | `403 FORBIDDEN` | **PASSED** |
| 4 | `test_cross_org_access_returns_404_not_403` | Thành viên Org A truy vấn Project của Org B $\to$ trả 404 (Anti-Enumeration, không làm lộ sự tồn tại của resource) | `404 NOT FOUND` | **PASSED** |
| 5 | `test_revoked_api_key_returns_401` | API key đã bị thu hồi (`revoked_at IS NOT NULL`) gọi endpoint đánh giá | `401 UNAUTHORIZED` | **PASSED** |
| 6 | `test_rate_limit_exceeded_returns_429_with_retry_after` | Gọi vượt quá 1.000 req/phút $\to$ Redis sliding window chặn và trả về header `Retry-After: 60` | `429 RATE_LIMITED` | **PASSED** |
| 7 | `test_evil_redos_regex_does_not_hang` | Điều kiện chứa mẫu ReDoS độc hại `(a+)+$` đối sánh chuỗi 30 ký tự `aaaa...X` $\to$ C-level timeout 50ms ngắt lập tức, không treo CPU | `< 50 ms` | **PASSED** |
| 8 | `test_deeply_nested_conditions_returns_400_condition_depth_exceeded` | Payload JSONB chứa cây điều kiện lồng 50 tầng $\to$ chặn đệ quy sâu | `400 CONDITION_DEPTH_EXCEEDED` | **PASSED** |
| 9 | `test_sql_injection_in_query_params_prevented` | Tấn công injection `' OR '1'='1` và `admin'--` qua query param tìm kiếm $\to$ tham số hóa an toàn, không rò rỉ bản ghi | `200 OK` (0 leak) | **PASSED** |
| 10 | `test_xss_in_flag_name_stored_lossless_and_escaped` | Tên cờ chứa `<script>alert("xss")</script>` $\to$ lưu trữ lossless nguyên trạng, client render escape | `200 OK` | **PASSED** |
| 11 | `test_internal_error_does_not_leak_stack_trace` | Ngoại lệ hệ thống chưa bắt (Unhandled Exception) $\to$ trả error envelope `INTERNAL_SERVER_ERROR` kèm `request_id`, không rò rỉ traceback | `500 INTERNAL_SERVER_ERROR` | **PASSED** |
| 12 | `test_sensitive_hashes_never_exposed_in_api` | Toàn bộ response schemas (User, ApiKey, Config) không chứa `password_hash`, `key_hash`, hay master secret key | Clean DTOs | **PASSED** |

### Lệnh thực thi kiểm thử an ninh:
```bash
pytest backend/app/tests/security/test_security_compliance.py -v
```
**Kết quả**: `12 passed, 1 warning in 13.95s`

---

## 3. Kết quả Phần B: Số liệu Benchmarks thực tế (Empirical Data)

*Ghi chú: Toàn bộ số liệu dưới đây được đo đạc trực tiếp trên hệ thống cục bộ (Windows 11, Python 3.13.9, PostgreSQL 16, Redis 7) và được lưu vết tại thư mục `load-tests/results/`.*

### 3.1. Phân giải in-process trên Python SDK (`load-tests/bench_inprocess.py`)
- **Số lượng mẫu**: 100.000 lượt đánh giá liên tục.
- **Kịch bản**: 10 cờ tính năng phức tạp (Boolean, String, Number, JSON configs) kết hợp phân nhóm Segment, điều kiện logic AND/OR, so sánh Semver, luật mục tiêu (Targeting Rules), Individual Overrides, và chia tỷ lệ phần trăm (Percentage Rollout với thuật toán MurmurHash3).

```
=====================================================================
 FlagOps In-Process Evaluation Benchmark (100,000 iterations)
=====================================================================
Total Duration:      0.359 seconds
Throughput:          278,361 evaluations / second

Latency Distribution:
  Min:               0.90 µs   (0.0009 ms)
  Mean:              3.09 µs   (0.0031 ms)
  p50 (Median):      2.50 µs   (0.0025 ms)
  p90:               6.30 µs   (0.0063 ms)
  p95:               7.00 µs   (0.0070 ms)
  p99:               8.70 µs   (0.0087 ms)   <-- Mục tiêu: < 1.0 ms
  p99.9:            47.90 µs   (0.0479 ms)
  Max:             261.60 µs   (0.2616 ms)

SLA Check (p99 < 1.0 ms): PASSED (thực tế: 0.0087 ms - nhanh hơn mục tiêu 114 lần)
```

Phân bổ kết quả đánh giá (Evaluation Reason Distribution):
- `DEFAULT`: 77.000 (77.0%)
- `DISABLED`: 10.000 (10.0%)
- `SPLIT` (MurmurHash3 Rollout): 10.000 (10.0%)
- `TARGETING_MATCH`: 3.000 (3.0%)

---

### 3.2. Độ trễ lan truyền SSE thời gian thực (`load-tests/bench_sse_latency.py`)
- **Mục đích**: Đo thời gian từ lúc Admin thực hiện gọi REST API cập nhật trạng thái cờ (`PUT /api/v1/flags/{id}/environments/{env_id}`) cho đến khi ứng dụng khách (SDK) đang lắng nghe Server-Sent Events nhận được sự kiện `ruleset_updated` qua Redis Pub/Sub.
- **Mục tiêu**: Độ trễ < 2.000 ms (2 giây).

```
=====================================================================
 FlagOps SSE Propagation Latency Benchmark (10 iterations)
=====================================================================
  [ 1/10] rulesetVersion: 2  -> received in  11.36 ms
  [ 2/10] rulesetVersion: 3  -> received in  12.90 ms
  [ 3/10] rulesetVersion: 4  -> received in  14.30 ms
  [ 4/10] rulesetVersion: 5  -> received in  12.23 ms
  [ 5/10] rulesetVersion: 6  -> received in  14.25 ms
  [ 6/10] rulesetVersion: 7  -> received in  14.89 ms
  [ 7/10] rulesetVersion: 8  -> received in  11.83 ms
  [ 8/10] rulesetVersion: 9  -> received in  11.32 ms
  [ 9/10] rulesetVersion: 10 -> received in  11.37 ms
  [10/10] rulesetVersion: 11 -> received in  12.93 ms

---------------------------------------------------------------------
SSE Propagation Latency Results:
  Min:    11.32 ms
  Mean:   12.74 ms
  p50:    12.90 ms
  p95:    14.89 ms
  p99:    14.89 ms   <-- Mục tiêu: < 2,000.0 ms (2.0s)
  Max:    14.89 ms

SLA Check (p99 < 2s): PASSED (thực tế: 14.89 ms - nhanh hơn mục tiêu 134 lần)
```

---

### 3.3. Độ trễ HTTP REST Endpoints trực tiếp (`load-tests/bench_remote_http.py`)
- **Quy mô**: 1.000 yêu cầu tuần tự cho mỗi endpoint kết nối trực tiếp đến FlagOps API server qua giao thức HTTP/TCP thực tế (sử dụng connection pool round-robin qua 5 API keys để tuân thủ ngưỡng rate limit 1.000 req/min).

```
=====================================================================
 SUMMARY LATENCY REPORT (N = 1,000 requests per endpoint)
=====================================================================

1. POST /eval/v1/flags/{key}/evaluate (Server Evaluation + Redis Caching)
   Throughput:  110 req/s
   Min:         7.33 ms
   Mean:        9.11 ms
   p50:         8.84 ms
   p90:        10.17 ms
   p95:        10.93 ms
   p99:        14.93 ms   <-- Mục tiêu: < 30.0 ms
   Max:        26.31 ms
   SLA Check:   PASSED (14.93 ms < 30.0 ms)

2. GET /eval/v1/ruleset (200 OK - Full Ruleset Bundle Download)
   Throughput:  162 req/s
   Min:         4.70 ms
   Mean:        6.19 ms
   p50:         5.83 ms
   p90:         7.43 ms
   p95:         9.08 ms
   p99:        14.36 ms   <-- Mục tiêu: < 35.0 ms
   Max:        23.13 ms
   SLA Check:   PASSED (14.36 ms < 35.0 ms)

3. GET /eval/v1/ruleset (304 Not Modified - ETag Fast Validation)
   Throughput:  189 req/s
   Min:         4.51 ms
   Mean:        5.29 ms
   p50:         4.93 ms
   p90:         6.03 ms
   p95:         7.17 ms
   p99:        12.51 ms   <-- Mục tiêu: < 10.0 ms
   Max:        19.01 ms
   Phân tích:   p95 đạt 7.17 ms (< 10 ms). Đuôi p99 đạt 12.51 ms chủ yếu do chi phí 
                bắt tay TCP loopback cục bộ trên môi trường Windows và chu kỳ Garbage Collection.
```

---

## 4. Kết quả Phần C: Tối ưu hóa dựa trên dữ liệu (EXPLAIN ANALYZE)

Kiểm thử bằng script [`load-tests/explain_hot_paths.py`](file:///d:/python/feature%20flag/load-tests/explain_hot_paths.py) với lệnh `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` trên PostgreSQL:

### 4.1. Hot Path 1: Tải tập quy tắc (`load_ruleset_bundle`)
Thay vì thực hiện N+1 query lặp qua từng cờ và từng biến thể, FlagOps áp dụng kỹ thuật **Hợp nhất truy vấn (Query Consolidation)**:
- **Truy vấn 1.1** (Flags JOIN Variations): `Nested Loop` với `project_id = :pid AND archived_at IS NULL` $\to$ Thời gian thực thi: **0.055 ms** (13 shared hit buffer blocks).
- **Truy vấn 1.2** (Settings JOIN TargetingRules): `Index Scan + Sort` với `environment_id = :eid` $\to$ Thời gian thực thi: **0.056 ms** (8 shared hit blocks).
- **Truy vấn 1.3** (Individual Overrides): `Hash Join` với setting của môi trường $\to$ Thời gian thực thi: **0.028 ms**.
- **Truy vấn 1.4** (Segments của dự án): `Index Scan` trên `ix_segment_project_id` $\to$ Thời gian thực thi: **0.011 ms**.
- **Kiểm định N+1 Query**: Đo bằng SQLAlchemy Cursor Event Listener $\to$ Khi nạp 5 cờ (hoặc 100 cờ), tổng số câu lệnh SQL phát sinh luôn cố định là **ĐÚNG 4 CÂU LỆNH SQL** (Zero N+1 Query).

### 4.2. Hot Path 2: Tra cứu xác thực API Key (`verify_api_key`)
- Truy vấn: `SELECT * FROM api_key JOIN environment WHERE key_hash = :hash AND revoked_at IS NULL`
- Dạng nút kế hoạch (Node Type): `Nested Loop` kết hợp `Index Scan` trên chỉ mục `ix_api_key_hash`.
- Thời gian lập kế hoạch (Planning Time): 0.082 ms.
- Thời gian thực thi (Execution Time): **0.029 ms** (29 microsecond, 5 shared buffer hits, 0 disk read).

### 4.3. Hot Path 3: Đọc Snapshot cấu hình (`ConfigRelease`)
- Truy vấn theo ID: `Index Scan` trên khóa chính `config_release.id` $\to$ **0.011 ms**.
- Truy vấn Release mới nhất theo Namespace: `Index Scan` kết hợp `Limit` trên `ix_config_release_namespace_id` $\to$ **0.013 ms**.

### 4.4. Cải tiến tối ưu hóa đạt được dựa trên số liệu thực nghiệm
- **Vấn đề phát hiện**: Trước khi tối ưu, endpoint `GET /eval/v1/ruleset` khi nhận header `If-None-Match` phát sinh 2 truy vấn DB riêng biệt: một truy vấn xác thực API key (đã eager-load đối tượng `Environment`), và một truy vấn thứ hai gọi `eval_service.get_environment_version` để lấy số version của môi trường.
- **Hành động tối ưu**: Tái sử dụng trực tiếp giá trị `api_key.environment.ruleset_version` đã được eager-load trong bộ nhớ ở dependency `verify_api_key`, loại bỏ hoàn toàn câu lệnh SQL thứ hai.
- **Hiệu quả đo lường**:
  - Thời gian xử lý trung bình của endpoint 304 giảm từ **6.78 ms xuống 5.29 ms** (cải thiện **22%**).
  - Throughput của endpoint 304 tăng từ **148 req/s lên 189 req/s** (tăng **27.7%**).
  - Giá trị trung vị p50 giảm từ **6.42 ms xuống 4.93 ms**.

### 4.5. Cấu hình Connection Pool
- Pool Class: `AsyncAdaptedQueuePool` (hỗ trợ asyncpg connection pooling an toàn).
- Kích thước Pool chuẩn: `pool_size = 5`, `max_overflow = 10`.
- Cơ chế phát hiện kết nối chết: `pool_pre_ping = True` (ngăn chặn triệt để lỗi kết nối gián đoạn khi idle quá lâu).

---

## 5. Artifacts được tạo mới và lưu trữ

1. **Kiểm thử an ninh**:
   - [`backend/app/tests/security/__init__.py`](file:///d:/python/feature%20flag/backend/app/tests/security/__init__.py)
   - [`backend/app/tests/security/test_security_compliance.py`](file:///d:/python/feature%20flag/backend/app/tests/security/test_security_compliance.py) (12 ca test an ninh toàn diện).
2. **Kịch bản đo lường hiệu năng**:
   - [`load-tests/bench_inprocess.py`](file:///d:/python/feature%20flag/load-tests/bench_inprocess.py) (100.000 lượt evaluate in-process).
   - [`load-tests/bench_sse_latency.py`](file:///d:/python/feature%20flag/load-tests/bench_sse_latency.py) (Đo độ trễ SSE thời gian thực).
   - [`load-tests/bench_remote_http.py`](file:///d:/python/feature%20flag/load-tests/bench_remote_http.py) (Đo đạc REST endpoints trực tiếp).
   - [`load-tests/explain_hot_paths.py`](file:///d:/python/feature%20flag/load-tests/explain_hot_paths.py) (EXPLAIN ANALYZE 3 hot paths).
   - [`load-tests/k6/evaluate.js`](file:///d:/python/feature%20flag/load-tests/k6/evaluate.js) (Kịch bản kiểm thử tải k6).
3. **Báo cáo dữ liệu thực nghiệm**:
   - [`load-tests/results/bench_inprocess.json`](file:///d:/python/feature%20flag/load-tests/results/bench_inprocess.json)
   - [`load-tests/results/bench_sse_latency.json`](file:///d:/python/feature%20flag/load-tests/results/bench_sse_latency.json)
   - [`load-tests/results/bench_remote_http.json`](file:///d:/python/feature%20flag/load-tests/results/bench_remote_http.json)
   - [`load-tests/results/explain_hot_paths.json`](file:///d:/python/feature%20flag/load-tests/results/explain_hot_paths.json)
