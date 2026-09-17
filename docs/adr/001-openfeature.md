# ADR-001: Tuân thủ Chuẩn CNCF OpenFeature và Khử Vendor Lock-in

## Trạng thái
Accepted

## Ngày
2026-09-17

## Ngữ cảnh (Context)
Trong kiến trúc phần mềm hiện đại và điện toán đám mây (Cloud-Native), Feature Flagging là một thành phần không thể thiếu của quá trình Continuous Integration / Continuous Deployment (CI/CD), Progressive Delivery và Trunk-Based Development. Tuy nhiên, một trong những nỗi lo lớn nhất của các giám đốc kỹ thuật (CTO) và đội ngũ Enterprise Architects là hiện tượng **Vendor Lock-in**:
- Mỗi nhà cung cấp dịch vụ Feature Flag (LaunchDarkly, Split, Flagsmith, Unleash, v.v.) đều cung cấp một bộ SDK độc quyền với giao diện lập trình (API surface) và quy ước hoàn toàn khác nhau.
- Nếu lập trình viên gọi trực tiếp SDK của một nhà cung cấp bên trong hàng trăm file mã nguồn dịch vụ:
  ```python
  # ❌ Gắn chặt code nghiệp vụ vào một thư viện SDK độc quyền
  from proprietary_vendor_sdk import VendorClient
  if vendor_client.is_feature_enabled("checkout-v2", user_id):
      render_new_checkout()
  ```
  Khi doanh nghiệp muốn tự chủ hạ tầng (self-hosted), tối ưu chi phí, hoặc chuyển sang một giải pháp khác, chi phí refactor mã nguồn và kiểm thử lại toàn bộ hệ thống là cực kỳ đắt đỏ, tiềm ẩn rủi ro hồi quy (regression risks).

## Quyết định (Decision)
Chúng tôi quyết định hiện thực hóa **FlagOps OpenFeature Provider** tuân thủ 100% đặc tả chuẩn **OpenFeature** của tổ chức **CNCF (Cloud Native Computing Foundation)**.

### 1. Phân tách Lớp: Ứng dụng khách chỉ tương tác với Chuẩn CNCF
Hệ thống FlagOps cung cấp lớp adapter `FlagOpsProvider` kế thừa từ `openfeature.provider.AbstractProvider`. Mã nguồn ứng dụng nghiệp vụ tuyệt đối không cần gọi trực tiếp `FlagOpsClient`, mà chỉ cần gọi thông qua giao diện chuẩn OpenFeature:

```python
from openfeature import api
from openfeature.evaluation_context import EvaluationContext
from flagops.openfeature import FlagOpsProvider

# Bước 1: Đăng ký FlagOps Provider (chỉ cần làm 1 lần ở điểm khởi động app)
api.set_provider(FlagOpsProvider(api_key="fo_srv_live_key", base_url="https://flagops.internal"))

# Bước 2: Ứng dụng chỉ phụ thuộc vào OpenFeature API chuẩn
client = api.get_client()
ctx = EvaluationContext(targeting_key="user-123", attributes={"country": "VN", "tier": "gold"})
is_v2_enabled = client.get_boolean_value("checkout-v2", False, ctx)
```

### 2. Chứng minh Khử Vendor Lock-in: Đổi Provider chỉ bằng ĐÚNG 1 DÒNG
Khả năng hoán đổi nhà cung cấp (Interoperability) được chứng minh thông qua cơ chế trừu tượng hóa của OpenFeature. Khi đội ngũ muốn chuyển đổi từ FlagOps sang `flagd` (Kubernetes in-cluster daemon của CNCF) hoặc bất kỳ nhà cung cấp nào khác, **chỉ cần đổi đúng 1 dòng khai báo provider**:

```python
# ── Cách 1: Sử dụng FlagOps Provider (Tự phát triển) ──────────────────────────
from flagops.openfeature import FlagOpsProvider
api.set_provider(FlagOpsProvider(api_key="fo_srv_...", base_url="http://localhost:8000"))

# ── Cách 2: Chuyển đổi sang Flagd Provider (CNCF daemon) — CHỈ 1 DÒNG DUY NHẤT ─
# from openfeature.contrib.provider.flagd import FlagdProvider
# api.set_provider(FlagdProvider(host="flagd.monitoring.svc", port=8013))

# ── Cách 3: Chuyển đổi sang In-Memory Provider phục vụ Unit Test ──────────────
# from openfeature.contrib.provider.in_memory import InMemoryFlagProvider
# api.set_provider(InMemoryFlagProvider({"checkout-v2": True}))

# ══> TOÀN BỘ CODE NGHIỆP VỤ PHÍA DƯỚI GIỮ NGUYÊN 100%, KHÔNG SỬA 1 KÝ TỰ:
client = api.get_client()
value = client.get_boolean_value("checkout-v2", False, ctx)
```

### 3. Thiết kế Wrapper tối giản (`ponytail`)
`FlagOpsProvider` không viết lại bất kỳ logic đánh giá nào mà đóng vai trò là một lớp mỏng (wrapper/adapter) bao quanh `FlagOpsClient`:
- **Tái sử dụng trọn vẹn**: Tận dụng engine in-process sub-millisecond, cache ruleset trong memory, luồng đồng bộ SSE, cơ chế nén HTTP ETag/304, exponential backoff và batch event buffer 10 giây của `FlagOpsClient`.
- **Ánh xạ lý do đánh giá (Reason Mapping)**:
  - FlagOps `TARGETING_MATCH` $\to$ OpenFeature `Reason.TARGETING_MATCH`
  - FlagOps `SPLIT` $\to$ OpenFeature `Reason.SPLIT`
  - FlagOps `DEFAULT` $\to$ OpenFeature `Reason.DEFAULT`
  - FlagOps `DISABLED` $\to$ OpenFeature `Reason.DISABLED`
  - FlagOps `ERROR` $\to$ OpenFeature `Reason.ERROR`
- **Ánh xạ mã lỗi chuẩn (ErrorCode Mapping)**:
  - `FLAG_NOT_FOUND`: Khi flag không có trong ruleset.
  - `TYPE_MISMATCH`: Khi kiểu dữ liệu yêu cầu không tương thích với kiểu cờ hoặc giá trị runtime (ví dụ: gọi `get_string_details` trên flag `BOOLEAN`).
  - `PROVIDER_NOT_READY`: Khi provider chưa hoàn thành việc nạp ruleset khởi đầu hoặc client chưa sẵn sàng.
  - `GENERAL`: Lỗi chung không xác định.
- **Ánh xạ ngữ cảnh mục tiêu (Context Translation)**:
  - Thuộc tính `targeting_key` trong `openfeature.EvaluationContext` được tự động ánh xạ thành `targetingKey` trong ngữ cảnh FlagOps, đảm bảo các thuật toán băm MurmurHash3 phân phối rollout theo tỷ lệ phần trăm (percentage rollout) và individual overrides hoạt động đồng nhất.

### 4. Triết lý Fail-Safe: Tuyệt đối không ném ngoại lệ
Tuân thủ nguyên tắc cốt lõi của OpenFeature và FlagOps SDK:
- Dù có xảy ra lỗi mạng, lỗi parse dữ liệu, flag không tồn tại hay sai lệch kiểu dữ liệu, provider **KHÔNG BAO GIỜ NÉM EXCEPTION** làm sập ứng dụng máy khách.
- Luôn trả về `default_value` kèm theo thông tin chi tiết về lỗi (`error_code`, `reason`, `error_message`) trong cấu trúc `FlagResolutionDetails`.

## Phương án thay thế (Alternatives Considered)

| Phương án | Ưu điểm | Nhược điểm | Kết luận |
|---|---|---|---|
| **Chỉ viết riêng SDK độc quyền của FlagOps** | Tự do sáng tạo API riêng, không cần tuân theo interface của bên thứ ba | Người dùng bị vendor lock-in; khó tích hợp vào các hệ sinh thái lớn đã chuẩn hóa OpenFeature; kém thuyết phục về mặt tiêu chuẩn công nghiệp | **Loại bỏ** |
| **Bỏ SDK độc quyền, chỉ viết OpenFeature Provider** | Chỉ cần duy trì một giao diện duy nhất | Người dùng muốn sử dụng các tính năng nâng cao (quản trị config namespace, xem diff ruleset trực tiếp) sẽ thiếu công cụ | **Loại bỏ** (Lựa chọn mô hình kép: FlagOps SDK native + OpenFeature Provider wrapper) |
| **Viết lại logic đánh giá bên trong Provider** | Không phụ thuộc vào FlagOpsClient | Nhân đôi mã nguồn (DRY violation), tiềm ẩn nguy cơ sai lệch kết quả (engine parity drift) | **Loại bỏ** |

## Hệ quả (Consequences)
- **Tích cực**:
  - Đồ án đạt chuẩn điện toán đám mây cao nhất (CNCF OpenFeature Specification).
  - Tránh hoàn toàn rủi ro vendor lock-in cho khách hàng doanh nghiệp.
  - Bộ kiểm thử đối chiếu (Parity Test) đảm bảo kết quả đánh giá qua OpenFeature Client và FlagOps SDK gốc là trùng khớp 100%.
  - Tích hợp mượt mà với toàn bộ hệ sinh thái OpenFeature Hooks, OpenTelemetry Tracing, và Logging.
- **Tiêu cực (Đã kiểm soát)**:
  - Cần cài đặt thêm package `openfeature-sdk`. (Gói nhẹ, phụ thuộc tối thiểu).
