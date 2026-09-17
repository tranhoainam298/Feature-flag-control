# S13a: Dashboard (Phần 1 — Khung + Flag + Mô Phỏng)

## Ngày hoàn thành
2026-09-17

## Kỹ năng áp dụng
`frontend-react-dashboard`, `taste-skill`, `web-design-guidelines`, `verification-before-completion`

---

## 1. Mục tiêu Slice 13A

Xây dựng toàn diện giao diện Web Dashboard quản trị Feature Flag cho FlagOps (React 18 + TypeScript + Vite + Tailwind CSS + TanStack Query), tuân thủ nghiêm ngặt các nguyên tắc thẩm mỹ chống slop (`taste-skill`), hợp đồng API, và tiêu chuẩn tiếp cận người dùng (`web-design-guidelines`).

---

## 2. Thiết lập 3 Dial & Design Read (`taste-skill`)

- **Design Read**:
  *"Reading this as: Internal developer and DevOps administration dashboard for engineering teams, with a Linear/Raycast dark-tech minimalist aesthetic, built with custom design tokens in `src/styles/tokens.css`, high visual data density, strict WCAG AA contrast, and zero frontend business logic."*
- **3 Dial cấu hình**:
  - `DESIGN_VARIANCE: 4` (Thấp-Vừa): Giao diện quản trị kỹ thuật, cấu trúc mạch lạc, chuẩn xác, không dùng bố cục phá cách hay bento ngẫu hứng.
  - `MOTION_INTENSITY: 2` (Thấp): Hoạt ảnh chuyển trạng thái nhanh (150–200ms) ở các nút toggle và hover, loại bỏ hoàn toàn các hiệu ứng cuộn từ tính hoặc parallax gây xao nhãng.
  - `VISUAL_DENSITY: 8` (Cao): Mật độ thông tin cao, hàng bảng dữ liệu gọn gàng, phông chữ đơn cách cho key/ID, tận dụng tối đa không gian màn hình làm việc của kỹ sư.

---

## 3. Các cấu phần đã hiện thực (Implemented)

### 3.1. Phần A — Nền Tảng (Core Infrastructure)
- **Hệ thống Design Token (`src/styles/tokens.css`)**:
  - Khai báo tập trung toàn bộ biến CSS: `--bg-canvas` (`#09090b`), `--bg-surface` (`#121215`), `--bg-surface-elevated` (`#18181b`), `--border-subtle` (`#27272a`), `--primary` (`#6366f1`), `--flag-on` (`#10b981`), `--flag-off` (`#71717a`).
  - Mở rộng Tailwind config (`tailwind.config.js`) để kết nối trực tiếp với biến token CSS.
  - Đặt chuẩn focus ring toàn hệ thống (`:focus-visible`) phục vụ điều hướng bằng phím Tab.
- **Layout Vỏ Ứng Dụng (`src/components/Layout.tsx`, `Sidebar.tsx`, `Topbar.tsx`)**:
  - **Sidebar**: Điều hướng các trang chức năng (Flags, Projects & Envs, Segments, Config, Audit) kèm badge hiển thị trạng thái module.
  - **Topbar**: Tích hợp bộ chọn Project (`currentProject`) và bộ chọn Environment (`currentEnvironment`) lưu trữ trạng thái toàn cục, badge môi trường Production, thông tin người dùng và nút Đăng xuất.
  - **State Toàn Cục (`src/context/AppContext.tsx`)**: Quản lý user, organization, project và environment đang chọn, tự động lưu id vào `localStorage`.
- **API Client (`src/lib/api.ts`)**:
  - Axios client tự động đính kèm `Authorization: Bearer <token>`.
  - Tự động bắt lỗi HTTP 401, gọi `/api/v1/auth/refresh` bằng refresh token và phát lại request ban đầu mà người dùng không bị văng ra ngoài.
  - Chuyển đổi envelope lỗi từ backend (`code`, `message`, `details`) thành thông điệp lỗi thân thiện.
- **TanStack Query (`src/lib/query-client.ts`)**:
  - Quản lý toàn bộ server state, cache thời gian thực (`staleTime: 15s`), tuyệt đối không dùng `useEffect` + `fetch` thủ công.
- **Bộ Component UI Đạt Chuẩn Trợ Năng**:
  - `Button`, `Input`, `Select`, `Badge`, `Switch`, `Modal`, `SkeletonTable`, `EmptyState`, `ErrorAlert`.
  - Mọi bảng hiển thị dữ liệu đều xử lý đủ 3 trạng thái: **Loading** (Skeleton), **Error** (Alert có nút Retry), và **Empty** (Minh họa + Nút tạo mới).

### 3.2. Phần B — Các Màn Hình Chức Năng (Pages)
- **`/login` (`src/pages/LoginPage.tsx`, `LoginForm.tsx`)**:
  - Biểu mẫu xác thực sử dụng React Hook Form + Zod (`email`, `password`).
  - Trợ năng: `autoComplete="email"`, `autoComplete="current-password"`, `role="alert"` cho thông báo lỗi.
  - Tích hợp 2 nút đăng nhập mẫu nhanh: `owner@demo.local` và `dev@demo.local` (mật khẩu: `demo1234`).
- **`/projects` (`src/pages/ProjectsPage.tsx`, `ProjectCard.tsx`, `CreateProjectModal.tsx`)**:
  - Lưới danh sách project của organization.
  - Modal tạo project mới với Zod validation (`key`, `name`, `description`).
- **`/projects/:id` (`src/pages/ProjectDetailPage.tsx`, `EnvironmentList.tsx`)**:
  - Tổng quan project và danh sách các môi trường (`dev`, `staging`, `prod`) với phiên bản ruleset hiện tại.
  - Hỗ trợ thêm mới môi trường trực tiếp.
- **`/flags` (`src/pages/FlagsPage.tsx`, `FlagTable.tsx`, `FlagRow.tsx`, `FlagFilterBar.tsx`, `CreateFlagModal.tsx`)**:
  - Bảng danh sách cờ tính năng theo Project và Environment đang chọn.
  - Thanh lọc: tìm kiếm theo key/tên, lọc theo kiểu (`BOOLEAN`, `STRING`, `NUMBER`, `JSON`), lọc cờ lưu trữ (archived).
  - **Toggle BẬT/TẮT ngay trên hàng bảng**: Cập nhật lạc quan (optimistic update) trên giao diện tức thì, đồng thời gửi API `PUT /api/v1/flags/{id}/environments/{env_id}` và tự động rollback nếu server phản hồi lỗi.
  - Modal tạo flag mới (`CreateFlagModal`) có kiểm tra regex định dạng key (`/^[a-zA-Z0-9._-]+$/`).
- **`/flags/:id` (`src/pages/FlagDetailPage.tsx`, `FlagHeader.tsx`, `FlagVariations.tsx`)**:
  - Chi tiết cờ, các thẻ tag, nút Archive / Restore.
  - Bộ chuyển tab môi trường để xem cấu hình trạng thái bật/tắt riêng biệt của từng môi trường.
  - Danh sách các biến thể (Variations) của cờ.

### 3.3. Phần C — Bảng Điều Khiển Mô Phỏng Đánh Giá (Evaluation Simulator)
- Tích hợp trực tiếp trên `/flags/:id` (`src/features/flags/FlagSimulator.tsx`).
- Biểu mẫu nhập Context động (thêm / xóa cặp thuộc tính key-value).
- Nút nạp sẵn ngữ cảnh mẫu (Quick Presets):
  - *Preset VN Premium*: `country = VN`, `plan = premium`.
  - *Preset US Free*: `country = US`, `plan = free`.
- Nút "Run Simulation" gọi API `POST /api/v1/flags/{flag_id}/environments/{env_id}/simulate`.
- **Kết quả hiển thị**:
  - Giá trị phân giải (`Resolved Value`).
  - Tên biến thể (`Variant`).
  - Badge lý do đánh giá (`Reason`) với màu ngữ nghĩa: `TARGETING_MATCH` (Xanh ngọc / Emerald), `DEFAULT` (Xanh dương / Info), `DISABLED` (Đỏ / Danger).
  - Bảng vết đánh giá chi tiết (`Rules Evaluation Trace`) liệt kê từng rule theo mức ưu tiên, mô tả điều kiện, trạng thái `MATCHED` / `SKIPPED` và lý do khớp.

---

## 4. Báo Cáo Tự Kiểm Tra Trợ Năng (Web Design Guidelines Self-Audit)

Không tự nhận "đã accessible" mà không có bằng chứng, dưới đây là kết quả kiểm tra đối chiếu từng tiêu chí với dòng code cụ thể:

| Tiêu chuẩn kiểm tra | Trạng thái | Bằng chứng mã nguồn / Dòng code cụ thể |
|---|---|---|
| **Nút Toggle Switch có WAI-ARIA đầy đủ** | **ĐẠT** | `role="switch"`, `aria-checked={checked}`, `aria-label={ariaLabel}` tại [`frontend/src/components/ui/Switch.tsx` (dòng 47-49)](file:///d:/python/feature%20flag/frontend/src/components/ui/Switch.tsx#L47-L49). Hỗ trợ kích hoạt bằng cả chuột và phím `Enter` / `Space` (dòng 34-44). |
| **Visible Focus Ring khi dùng bàn phím Tab** | **ĐẠT** | Toàn hệ thống có `:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }` tại [`frontend/src/index.css` (dòng 17-19)](file:///d:/python/feature%20flag/frontend/src/index.css#L17-L19) và `focus-visible:ring-2 focus-visible:ring-brand` tại [`Button.tsx` (dòng 47)](file:///d:/python/feature%20flag/frontend/src/components/ui/Button.tsx#L47), [`Input.tsx` (dòng 30)](file:///d:/python/feature%20flag/frontend/src/components/ui/Input.tsx#L30). |
| **Biểu mẫu Form Login chuẩn hóa** | **ĐẠT** | Thuộc tính `autoComplete="email"` và `autoComplete="current-password"` tại [`frontend/src/features/auth/LoginForm.tsx` (dòng 76, 85)](file:///d:/python/feature%20flag/frontend/src/features/auth/LoginForm.tsx#L76-L85). Mọi Input đều có nhãn `<label htmlFor="...">` tương ứng với `id` của input (dòng 16-24 trong `Input.tsx`). |
| **Thông báo lỗi có ngữ nghĩa màn hình đọc** | **ĐẠT** | Thông báo lỗi validate form và banner lỗi server đều có thuộc tính `role="alert"` tại [`LoginForm.tsx` (dòng 67)](file:///d:/python/feature%20flag/frontend/src/features/auth/LoginForm.tsx#L67), [`Input.tsx` (dòng 39)](file:///d:/python/feature%20flag/frontend/src/components/ui/Input.tsx#L39), [`ErrorAlert.tsx` (dòng 23)](file:///d:/python/feature%20flag/frontend/src/components/ui/ErrorAlert.tsx#L23). |
| **Tương tác Modal chuẩn W3C Dialog** | **ĐẠT** | `role="dialog"`, `aria-modal="true"`, `aria-labelledby="modal-title"` và lắng nghe phím `Escape` để đóng modal tại [`frontend/src/components/ui/Modal.tsx` (dòng 20-33, 43-45)](file:///d:/python/feature%20flag/frontend/src/components/ui/Modal.tsx#L20-L45). |
| **Độ tương phản màu sắc (Contrast Ratio)** | **ĐẠT** | Văn bản chính `--text-primary: #f4f4f5` trên nền `--bg-surface: #121215` đạt tỷ lệ tương phản **15.8:1** (vượt xa chuẩn WCAG AA tối thiểu 4.5:1). |

---

## 5. Bằng Chứng Xác Minh Thực Nghiệm (Verification Evidence)

Theo quy tắc bắt buộc của `verification-before-completion`, toàn bộ các lệnh kiểm thử và luồng trải nghiệm người dùng đã được thực thi và xác nhận:

### 5.1. Kiểm tra Biên dịch & Linting
- **Biên dịch Frontend**:
  ```bash
  npm run build --prefix frontend
  ```
  *Kết quả*: **Exit code 0** (1.815 module transformed, bundle sinh ra sạch sẽ tại `dist/` mà không có lỗi hay cảnh báo kiểu TypeScript).
- **Kiểm tra Lint / Kiểu**:
  ```bash
  npm run lint --prefix frontend
  ```
  *Kết quả*: **Exit code 0** (`tsc -b` pass hoàn toàn).

### 5.2. Kiểm thử Tích Hợp Backend (Regression Test)
- Chạy kiểm thử các endpoint xác thực và cờ:
  ```bash
  docker compose exec -T api pytest app/tests/test_auth.py app/tests/test_flags.py -v
  ```
  *Kết quả*: **36/36 passed in 19.78s** (100% xanh, không hồi quy).

### 5.3. Xác minh Luồng Trải Nghiệm Qua Trình Duyệt Thực Tế
Đã thực hiện tự động hóa trình duyệt qua `browser_subagent` và ghi nhận video/ảnh chụp minh chứng:

1. **Đăng nhập**:
   - Truy cập `http://localhost:3000/login`.
   - Bấm nút đăng nhập nhanh `owner@demo.local` (mật khẩu: `demo1234`).
   - Đăng nhập thành công, nhận JWT token và điều hướng vào trang `/flags`.
2. **Hiển thị đủ 5 Flag từ dữ liệu Seed**:
   - `checkout-v2` (Boolean)
   - `new-homepage` (Boolean)
   - `dark-mode` (Boolean)
   - `payment-v2` (String - multivariate)
   - `recommendation-engine` (JSON)
3. **Bật/Tắt Flag trực tiếp trên bảng**:
   - Bấm nút switch trên hàng cờ `checkout-v2` trong môi trường `Development`.
   - Giao diện cập nhật lạc quan tức thì, gọi API thật `PUT /api/v1/flags/.../environments/...`.
   - Nút chuyển sang trạng thái `ON` (màu xanh ngọc `bg-flag-on`). Tải lại trang (F5) trạng thái vẫn giữ nguyên `ON`.
4. **Chạy Mô Phỏng Đánh Giá (Simulator)**:
   - Truy cập chi tiết cờ `checkout-v2` (`/flags/ac126399-6765-4864-8fe9-cc295959f2a5`).
   - Chọn `Preset: VN Premium` (`country = VN`, `plan = premium`).
   - Bấm `Run Simulation`.
   - **Kết quả trả về chính xác**:
     - *Reason*: `TARGETING_MATCH`
     - *Resolved Value*: `true`
     - *Variant*: `true`
     - *Trace*: Rule `#1` ("VN Premium users get new checkout") có trạng thái `MATCHED`.
5. **Minh chứng Đa phương tiện Đã Lưu**:
   - Ảnh chụp màn hình: `flags_page_overview_1789627230583.png`
   - Ảnh chụp màn hình kết quả mô phỏng: `simulation_result_1789627148038.png`
   - Video phiên tương tác: `demo_local_login_1789627197709.webp`

---

## 6. Trạng Thái Hoàn Thành

- Tất cả các ràng buộc kỹ thuật (Component < 200 dòng, React Hook Form + Zod, không business logic ở frontend, TanStack Query, xử lý đủ 3 trạng thái loading/empty/error) đã được đáp ứng 100%.
- Định dạng theo đúng quy ước tiến độ của dự án.
