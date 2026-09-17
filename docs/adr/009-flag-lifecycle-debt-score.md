# ADR-009: Quản lý vòng đời Feature Flag và Thuật toán Điểm nợ Kỹ thuật (Debt Score)

## Trạng thái
Accepted

## Ngày
2026-09-17

## Ngữ cảnh (Context)
Trong các hệ thống quản trị cờ tính năng công nghiệp (LaunchDarkly, Flagsmith, Unleash), một trong những thách thức lớn nhất sau thời gian dài vận hành là **nợ kỹ thuật do cờ tính năng tồn đọng (Feature Flag Technical Debt)**. 
- Các cờ thử nghiệm hoặc tạm thời sau khi hoàn tất rollout 100% thường bị lãng quên trong mã nguồn ("zombie flags").
- Mã nguồn phân nhánh phức tạp, khó kiểm thử, tiềm ẩn rủi ro logic ngoài ý muốn.
- Chi phí bảo trì tăng cao, gây quá tải cho các kỹ sư mới tham gia dự án.

Đồ án **FlagOps** xác định đây là **Điểm khác biệt học thuật số 1**: xây dựng cơ chế tự động đánh giá sức khỏe, suy diễn trạng thái vòng đời động, và lượng hóa nợ kỹ thuật thành một chỉ số định lượng rõ ràng từ 0 đến 100 kèm các khuyến nghị hành động dọn dẹp.

## Quyết định (Decision)

### 1. Suy diễn trạng thái vòng đời động (Derived Lifecycle State)
Thay vì lưu cứng trạng thái vào cơ sở dữ liệu và phụ thuộc vào cron job để cập nhật thủ công, trạng thái vòng đời được suy diễn động theo dữ liệu thực tế tại thời điểm truy vấn:
- `DRAFT`: Cờ chưa bật ở bất kỳ môi trường nào (`enabled_env_count == 0`).
- `ACTIVE`: Cờ đang bật ở ≥ 1 môi trường nhưng rollout tại production chưa đạt 100%.
- `ROLLED_OUT`: Cờ đã bật và phân phối rollout 100% tại production.
- `STALE`: Cờ thỏa mãn một trong các điều kiện:
  1. Duy trì `ROLLED_OUT` liên tục vượt quá ngưỡng `stale_days` của project (mặc định 30 ngày).
  2. Không nhận được bất kỳ sự kiện đánh giá (evaluation event) nào trong vòng 14 ngày.
  3. Là cờ tạm thời (`is_temporary = True`) và đã quá hạn sử dụng.
- `ARCHIVED`: Cờ có `archived_at` khác null.

### 2. Thuật toán Pure Debt Score độc lập không I/O
Tách biệt triệt để tầng tính toán điểm số thành mô-đun Python thuần khiết `backend/app/services/flag_debt.py`:
- Công thức tính điểm nợ:
  $$\text{Debt Score} = \mathrm{round}\left(w_{\text{age}} \cdot S_{\text{age}} + w_{\text{rollout}} \cdot S_{\text{rollout}} + w_{\text{staleness}} \cdot S_{\text{staleness}} + w_{\text{temp}} \cdot S_{\text{temp}}\right)$$
- Các hàm tính điểm thành phần:
  - $S_{\text{age}} = \min(100, \frac{\text{age\_days}}{365} \cdot 100)$
  - $S_{\text{rollout}} = \min(100, \frac{\text{days\_at\_full\_rollout}}{\text{stale\_days}} \cdot 100)$
  - $S_{\text{staleness}} = 100 \text{ (nếu không eval > 14 ngày)}$ hoặc $\min(100, \frac{\text{days\_since\_last\_eval}}{14} \cdot 100)$
  - $S_{\text{temp}} = 100 \text{ (nếu is\_temporary và vượt stale\_days)}$ hoặc $50 \text{ (nếu is\_temporary)}$ hoặc $0$.
- Các trọng số $w$ được cấu hình linh hoạt từ môi trường qua `Settings` (`DEBT_W_AGE=0.25`, `DEBT_W_ROLLOUT=0.35`, `DEBT_W_STALENESS=0.25`, `DEBT_W_TEMPORARY=0.15`), đảm bảo $\sum w = 1.0$.

### 3. Tách biệt I/O Service và API Layer
- `flag_health.py` service chịu trách nhiệm truy vấn DB, tải cấu hình môi trường production, đếm số lượt evaluation, tổng hợp thành `FlagSnapshot` bất biến và gửi vào hàm `calculate_debt_score`.
- API cung cấp endpoint phân tích sức khỏe đa chiều và thao tác `archive` cờ (ghi audit log).

## Phương án thay thế (Alternatives Considered)

| Tiêu chí | Phương án đã chọn (Derived Real-time) | Chạy Cron Job định kỳ lưu DB | Giao diện tự tính (Frontend logic) |
|---|---|---|---|
| **Độ tươi của dữ liệu** | Tức thì (Real-time), chính xác 100% khi người dùng truy cập | Chậm trễ, phụ thuộc tần suất chạy job (ví dụ: chạy hàng giờ hoặc hàng ngày) | Phụ thuộc dữ liệu cache client |
| **Độ phức tạp hạ tầng** | Đơn giản, không cần worker/scheduler riêng (tinh thần Ponytail/YAGNI) | Phức tạp: cần Redis Celery / APScheduler worker, quản lý race condition và lock | Dễ lỗi, không bảo vệ được tính nhất quán giữa API và Web |
| **Khả năng kiểm thử (Testability)** | Rất cao: Pure functions kiểm thử 100% bằng unit tests độc lập | Khó kiểm thử vì phụ thuộc DB states và timing của job | Khó kiểm thử tích hợp |

## Hệ quả (Consequences)
- **Tích cực**:
  - Đảm bảo tính nhất quán (consistent) và không có độ trễ giữa trạng thái thực tế của cờ và điểm nợ hiển thị.
  - Mã nguồn tính toán điểm nợ không có side effects, kiểm thử đạt độ phủ 100% với 27 tests tự động.
  - Tối ưu hiệu năng: tính toán toán học ma trận nhẹ nhàng chỉ mất dưới 1ms cho hàng trăm cờ.
- **Tiêu cực**:
  - Khi số lượng cờ trong dự án lên đến hàng ngàn, việc truy vấn bảng events để đếm ngày evaluation có thể tăng tải I/O nếu không đánh chỉ mục (index) thích hợp trên `evaluation_events(flag_id, created_at)`. Đã bổ sung composite index cho bảng này.
