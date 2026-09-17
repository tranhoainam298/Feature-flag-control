# S13b: Dashboard (Phần 2 — Rule Builder + Config Center + Audit Logs)

## Ngày hoàn thành
2026-09-17

## Kỹ năng áp dụng
`frontend-react-dashboard`, `taste-skill`, `web-design-guidelines`, `verification-before-completion`

---

## 1. Mục tiêu Slice 13B

Hoàn thiện toàn bộ các chức năng quản trị nâng cao của FlagOps Dashboard:
- **Phần A — Rule Builder & Segments**: Xây dựng trình dựng quy tắc targeting theo độ ưu tiên, phân phối rollout dạng slider, cảnh báo đỏ khi tổng tỉ lệ khác 100%, chế độ JSON nâng cao, quản lý phân khúc người dùng (Segments) dùng chung bộ soạn điều kiện.
- **Phần B — Config Center**: Bảng quản lý cấu hình key-value sửa tại chỗ, badge cảnh báo thay đổi chưa phát hành, modal xem diff 3 cột (added / changed / removed), xuất bản release kèm comment, xem lịch sử phiên bản, so sánh 2 bản bất kỳ, rollback phiên bản có xác nhận, che giấu secret và nút giải mã con mắt.
- **Phần C — Audit Logs**: Bảng nhật ký kiểm toán với bộ lọc đa tiêu chí, phân trang cursor, xem chi tiết thay đổi Before / After dạng diff JSON.

---

## 2. Thiết lập Thẩm mỹ & 3 Dial (`taste-skill`)

- **Design Direction**:
  *Internal developer and DevOps administration platform. Minimalist dark-tech theme, Linear/Raycast aesthetic, strict WCAG AA contrast, custom design tokens in `src/styles/tokens.css`, visual density tối đa cho dữ liệu kỹ thuật, zero frontend business logic.*
- **3 Dial cấu hình**:
  - `DESIGN_VARIANCE: 4` (Thấp-Vừa): Bố cục thanh thoát, gọn gàng, tôn trọng chuẩn mực quản trị, không phá vỡ luồng thao tác kỹ sư.
  - `MOTION_INTENSITY: 2` (Thấp): Hoạt ảnh tức thì (150–200ms) khi hover, mở modal và chuyển tab.
  - `VISUAL_DENSITY: 8` (Cao): Mật độ thông tin cao, phông monospace cho key/ID/JSON diff, tận dụng màn hình cho bảng và so sánh dữ liệu.

---

## 3. Các cấu phần đã hiện thực (Implemented)

### 3.1. Phần A — Rule Builder & Segments
- **Trình soạn điều kiện (`src/components/conditions/ConditionRow.tsx`, `ConditionGroup.tsx`)**:
  - Hỗ trợ toán tử logic `ALL (AND)` và `ANY (OR)`.
  - Danh sách cố định 14 toán tử chuẩn: `EQ`, `NEQ`, `IN`, `NOT_IN`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `GT`, `LT`, `GTE`, `LTE`, `IS_TRUE`, `IS_FALSE`, `MATCHES_REGEX`.
  - Tự động parse mảng JSON cho `IN`/`NOT_IN` hoặc split phẩy linh hoạt.
- **Phân phối Rollout (`src/features/targeting/DistributionEditor.tsx`)**:
  - Sliders và ô nhập số trực quan cho từng variation.
  - Nút tiện ích "Chia đều" (Even split) và gán nhanh 100% cho từng variation.
  - Hiển thị tổng phần trăm thời gian thực. **Cảnh báo đỏ (Red Alert Badge + Banner)** nổi bật khi `tổng != 100%`.
- **Thẻ Quy tắc (`src/features/targeting/RuleCard.tsx`)**:
  - Hiển thị thứ tự ưu tiên `#1, #2...`.
  - Nút di chuyển lên/xuống đổi độ ưu tiên tuần tự.
  - Nút xóa quy tắc, mô tả tùy chọn, tích hợp `ConditionGroup` và `DistributionEditor`.
- **Chế độ JSON nâng cao (`src/features/targeting/JsonRuleEditor.tsx`)**:
  - Cho phép dán/chỉnh sửa mảng JSON rules trực tiếp làm phương án dự phòng.
  - Kiểm tra cú pháp thời gian thực, nút "Định dạng JSON" và "Áp dụng thay đổi".
- **Bộ điều phối (`src/features/targeting/RuleBuilder.tsx`)**:
  - Nút thêm quy tắc mới.
  - Nút "Lưu tất cả quy tắc" gọi atomic `PUT /api/v1/flags/{id}/environments/{envId}/rules`.
  - Hiển thị chính xác thông điệp lỗi validate 422 từ backend.
- **Tích hợp Tab Flag Detail (`src/pages/FlagDetailPage.tsx`)**:
  - Tách 3 tab rõ ràng: `Targeting & Quy tắc`, `Mô phỏng đánh giá (Simulator)`, `Variations & Tổng quan`.
- **Quản lý Segments (`src/pages/SegmentsPage.tsx`, `SegmentCard.tsx`, `CreateSegmentModal.tsx`)**:
  - Tái sử dụng `ConditionGroup` để định nghĩa tiêu chí phân khúc người dùng.
  - Hiển thị danh sách segment dạng card với tổng số điều kiện và JSON snapshot.
  - Hỗ trợ tạo mới và xóa segment có xác nhận.

### 3.2. Phần B — Config Center
- **Trang danh sách Namespace (`src/pages/ConfigPage.tsx`, `NamespaceCard.tsx`, `CreateNamespaceModal.tsx`)**:
  - Quản lý namespaces theo từng môi trường làm việc.
  - Tạo mới namespace với định dạng JSON, YAML hoặc PROPERTIES.
  - Hiển thị badge trạng thái phiên bản hiện tại.
- **Chi tiết Namespace (`src/pages/ConfigDetailPage.tsx`)**:
  - Chuyển đổi giữa 2 tab: `Bản nháp hiện tại (Draft)` và `Lịch sử phát hành (Releases)`.
- **Bảng cấu hình nháp sửa tại chỗ (`src/features/config/ConfigDraftTable.tsx`)**:
  - In-place editing cho Key, Value, Type (`STRING`, `NUMBER`, `BOOLEAN`, `JSON`), Secret toggle, Comment.
  - Nút "Thêm khóa cấu hình", nút xóa từng khóa.
  - Badge cảnh báo nổi bật: `Có N thay đổi chưa phát hành` khi nháp khác release hiện tại.
  - Nút "Lưu nháp" gọi `PUT /api/v1/namespaces/{n}/items`.
  - Bảo mật: Item secret hiển thị dạng `••••••••` kèm icon ổ khóa. Nút "Hiện/Ẩn secret" gọi API kèm query param `reveal=true` (chỉ role đủ quyền).
- **Modal so sánh Diff 3 cột (`src/features/config/ConfigDiffModal.tsx`)**:
  - Cột 1 (Xanh lá - Added): Hiển thị các key và giá trị mới được thêm.
  - Cột 2 (Vàng hổ phách - Changed): Hiển thị các key bị sửa với giá trị cũ (`-`) và mới (`+`).
  - Cột 3 (Đỏ - Removed): Hiển thị các key bị xóa gạch ngang.
- **Phát hành Release (`src/features/config/PublishReleaseModal.tsx`)**:
  - Nhập comment phát hành, gọi `POST /api/v1/namespaces/{n}/releases`.
- **Lịch sử & Rollback (`src/features/config/ReleaseHistoryTable.tsx`, `CompareReleasesModal.tsx`)**:
  - Bảng lịch sử release kèm badge `Hiện tại` và `Rollback`.
  - Nút "So sánh 2 phiên bản" cho phép chọn 2 version bất kỳ để xem diff 3 cột.
  - Nút "Rollback" có hộp thoại xác nhận an toàn, gọi `POST /api/v1/namespaces/{n}/releases/{v}/rollback`, tự động đồng bộ lại draft.

### 3.3. Phần C — Audit Logs
- **Backend Router (`backend/app/api/v1/audit.py`)**:
  - Endpoint `GET /api/v1/audit` với các bộ lọc `project_id`, `environment_id`, `actor_id`, `action`, `entity_type`.
  - Phân trang cursor `id < cursor` tối ưu cho bảng dữ liệu lớn.
  - Pydantic v2 `field_validator(mode="before")` serialize an toàn IPv4/IPv6 `ip_address`.
- **Giao diện Audit (`src/pages/AuditPage.tsx`, `src/features/audit/AuditTable.tsx`, `AuditDetailModal.tsx`)**:
  - Bảng nhật ký với badge màu phân loại hành động (`created`, `updated`, `deleted`, `rollback`, `published`).
  - Lọc theo chuỗi hành động và dropdown loại đối tượng (`flag`, `config_namespace`, `targeting_rule`, etc.).
  - Phân trang cursor với nút "Trang kế tiếp" và "Về trang đầu".
  - Bấm vào bất kỳ dòng nào mở modal chi tiết: hiển thị siêu dữ liệu và hai cột Before / After dạng diff JSON.

---

## 4. Kết quả Kiểm thử & Bằng chứng (Verification Evidence)

### 4.1. TypeScript Compilation & Bundle Build
```powershell
npm run build --prefix frontend
```
**Kết quả**: Exit code 0, không còn bất kỳ cảnh báo hay lỗi kiểu dữ liệu nào.
- 1,840 modules transformed
- `dist/index.html`: 0.55 kB
- `dist/assets/index-DYOP5IyQ.css`: 26.48 kB
- `dist/assets/index-wRFpXbo6.js`: 571.19 kB

### 4.2. Triển khai Docker Container
Toàn bộ artifact `dist/` được đồng bộ trực tiếp vào web container đang chạy:
```powershell
docker cp frontend/dist/. flagops-web:/usr/share/nginx/html/
```
Nginx container phục vụ trực tiếp tại `http://localhost:3000`.

### 4.3. Kiểm thử Tự động qua Browser Subagent
Quá trình kiểm thử UI toàn diện được ghi hình tại:
`slice13b_demo_1789628173290.webp`

1. **Chuỗi Feature Flag & Targeting Rules**:
   - Truy cập `/flags`, chọn cờ `checkout-v2`.
   - Chuyển tab `Targeting & Quy tắc`, hiển thị đầy đủ quy tắc điều kiện và phân phối.
   - Nhấn "Chia đều" để cân bằng 50% / 50% giữa các variation.
   - Nhấn "Lưu tất cả quy tắc", hệ thống xác nhận lưu thành công và cập nhật server state.
   - Chuyển tab `Mô phỏng đánh giá (Simulator)`, nạp context mẫu VN Premium và thực hiện mô phỏng. Kết quả đánh giá khớp chính xác với rule.
   - Ảnh chụp màn hình: `simulation_result_1789628308471.png`.
2. **Chuỗi Config Center (Draft -> Diff -> Publish -> History -> Rollback)**:
   - Truy cập `/config`, chọn namespace `payment-service`.
   - Thêm key cấu hình `max_retry = 5`, lưu nháp.
   - Badge "Có 1 thay đổi chưa phát hành" hiển thị dạng pulse cảnh báo.
   - Mở modal "Xem thay đổi (Diff)", kiểm tra cột Added hiển thị `+max_retry: 5`.
   - Nhấn "Tiến hành phát hành", nhập ghi chú *"Update max_retry configuration"*, xác nhận phát hành thành `v4`.
   - Badge cập nhật về "Đồng bộ với bản phát hành hiện tại".
   - Chuyển tab `Lịch sử phát hành (Releases)`, hiển thị phiên bản `v4` ở đầu bảng.
   - Nhấn nút "Rollback" về phiên bản `v3`, xác nhận cảnh báo. Bản rollback được tạo lập tức, số lượng item trong draft quay về 3 khóa như cũ.
3. **Chuỗi Audit Logs**:
   - Truy cập `/audit`.
   - Toàn bộ các thao tác vừa thực hiện (`config.draft_updated`, `config.release_published`, `config.rollback`, `flag_rule_updated`) đều hiển thị theo thứ tự thời gian.
   - Nhấp vào dòng audit log đầu tiên, mở modal hiển thị đầy đủ thông tin: Actor ID, IP Address, Action và hai cột Before / After JSON snapshot.

---

## 5. Kết luận

Slice 13B đã hoàn thành 100% các tiêu chí trong Definition of Done:
- Rule Builder hoạt động chuẩn xác, có cảnh báo 100% và chế độ JSON dự phòng.
- Segments tái sử dụng chung bộ soạn điều kiện.
- Config Center hoàn thiện chu trình nháp -> diff 3 cột -> publish -> rollback.
- Audit Log hiển thị trước/sau minh bạch và hỗ trợ phân trang cursor mượt mà.
- Mã nguồn sạch sẽ, tuân thủ nguyên tắc một chiều và thẩm mỹ anti-slop.
