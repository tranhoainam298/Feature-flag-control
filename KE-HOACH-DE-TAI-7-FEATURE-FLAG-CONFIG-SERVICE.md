# ĐỀ TÀI 7 — DỊCH VỤ QUẢN TRỊ FEATURE FLAG VÀ CẤU HÌNH ỨNG DỤNG
### Tài liệu khảo sát mã nguồn mở + Kế hoạch triển khai chi tiết
**Sinh viên CNTT – định hướng Công nghệ phần mềm · Đại học Duy Tân**
Phiên bản 1.0 · 16/09/2026

---

## MỤC LỤC

- [PHẦN A. Hiểu đúng đề tài](#phần-a-hiểu-đúng-đề-tài)
- [PHẦN B. Khảo sát mã nguồn mở trên GitHub](#phần-b-khảo-sát-mã-nguồn-mở-trên-github)
- [PHẦN C. Chiến lược chọn "gốc" để phát triển](#phần-c-chiến-lược-chọn-gốc-để-phát-triển)
- [PHẦN D. Phạm vi hệ thống (Scope)](#phần-d-phạm-vi-hệ-thống-scope)
- [PHẦN E. Kiến trúc hệ thống](#phần-e-kiến-trúc-hệ-thống)
- [PHẦN F. Mô hình dữ liệu chi tiết](#phần-f-mô-hình-dữ-liệu-chi-tiết)
- [PHẦN G. Thuật toán đánh giá flag](#phần-g-thuật-toán-đánh-giá-flag)
- [PHẦN H. Thiết kế API](#phần-h-thiết-kế-api)
- [PHẦN I. SDK và chuẩn OpenFeature](#phần-i-sdk-và-chuẩn-openfeature)
- [PHẦN J. Module quản trị cấu hình](#phần-j-module-quản-trị-cấu-hình)
- [PHẦN K. Điểm khác biệt học thuật](#phần-k-điểm-khác-biệt-học-thuật)
- [PHẦN L. Công nghệ sử dụng](#phần-l-công-nghệ-sử-dụng)
- [PHẦN M. Kế hoạch 15 tuần](#phần-m-kế-hoạch-15-tuần)
- [PHẦN N. Phân công nhóm](#phần-n-phân-công-nhóm)
- [PHẦN O. Kế hoạch kiểm thử](#phần-o-kế-hoạch-kiểm-thử)
- [PHẦN P. DevOps & CI/CD](#phần-p-devops--cicd)
- [PHẦN Q. Rủi ro và phương án xử lý](#phần-q-rủi-ro-và-phương-án-xử-lý)
- [PHẦN R. Sản phẩm bàn giao](#phần-r-sản-phẩm-bàn-giao)
- [PHẦN S. Checklist tuần 1](#phần-s-checklist-tuần-1)

---

## PHẦN A. HIỂU ĐÚNG ĐỀ TÀI

### A.1. Tên đề tài tách làm hai vế

> **"Dịch vụ quản trị feature flag"** + **"và cấu hình ứng dụng"**

Đây là **hai module** chứ không phải một. Rất nhiều nhóm làm sai ở bước này: chỉ làm feature flag rồi bỏ quên vế thứ hai, dẫn tới mất điểm phạm vi khi bảo vệ.

| Vế | Bản chất | Câu hỏi nó trả lời |
|---|---|---|
| **Feature Flag** (Feature Toggle) | Bật/tắt **hành vi** của tính năng tại runtime, không cần deploy lại | "Tính năng X có được bật cho người dùng này không?" |
| **Application Configuration** (Remote Config / Config Center) | Quản lý **giá trị tham số** tập trung, có version và rollback | "Giá trị `payment.timeout_ms` ở môi trường prod hiện là bao nhiêu?" |

Hai vế này chia sẻ chung rất nhiều hạ tầng (môi trường, phân quyền, audit, SDK, cơ chế đẩy cập nhật realtime) nên gộp vào một hệ thống là hợp lý — và đó chính là ý đồ của đề tài.

### A.2. Bài toán nghiệp vụ thực tế

Vấn đề mà hệ thống này giải quyết:

1. **Tách deploy khỏi release.** Code lên production nhưng tính năng vẫn tắt. Khi nào sẵn sàng thì bật — không cần build lại.
2. **Rollout dần (canary/progressive delivery).** Bật cho 1% → 5% → 25% → 100%. Có sự cố thì tắt trong 5 giây thay vì rollback deploy 30 phút.
3. **Kill switch.** Tính năng gây sự cố → tắt ngay lập tức.
4. **A/B testing.** Chia người dùng thành các nhánh variant để so sánh.
5. **Cấu hình không nằm trong code.** Không phải sửa `.env` rồi restart 20 pod. Đổi trên dashboard, ứng dụng nhận trong vài giây.
6. **Truy vết.** Ai đổi cái gì, lúc nào, vì sao, và rollback về đâu.

### A.3. Khái niệm nền tảng cần nắm (phục vụ chương 2 báo cáo)

- **Flag / Toggle**: một công tắc có định danh (`key`), thuộc về một project.
- **Variation**: các giá trị khả dĩ của flag (boolean: `on`/`off`; multivariate: `control`/`variant_a`/`variant_b`).
- **Environment**: `development` / `staging` / `production`. Cùng một flag nhưng trạng thái độc lập theo môi trường.
- **Segment**: nhóm người dùng được định nghĩa bởi điều kiện (`country == "VN" AND plan == "premium"`).
- **Targeting Rule**: luật gán variation cho người dùng thỏa điều kiện.
- **Percentage Rollout**: chia phần trăm lưu lượng, phải **ổn định (sticky)** — cùng một user luôn rơi vào cùng một nhánh.
- **Evaluation Context**: dữ liệu về người dùng gửi kèm lúc đánh giá (`userId`, `email`, `country`, `appVersion`...).
- **Evaluation Reason**: lý do trả về kết quả đó (`TARGETING_MATCH`, `SPLIT`, `DEFAULT`, `DISABLED`, `ERROR`) — bắt buộc phải có để debug.
- **Flag Debt / Stale Flag**: flag đã 100% rollout nhưng chưa xóa khỏi code — nợ kỹ thuật tích tụ.
- **Namespace** (phía config): nhóm cấu hình theo service/module.
- **Release**: bản phát hành cấu hình đã đóng băng, có số version, có thể rollback.

Phân loại toggle theo Martin Fowler — nên trích dẫn trong báo cáo:
`Release Toggle` (tạm, vòng đời ngắn) · `Experiment Toggle` (A/B) · `Ops Toggle` (kill switch) · `Permission Toggle` (bật theo nhóm user, sống lâu).

---

## PHẦN B. KHẢO SÁT MÃ NGUỒN MỞ TRÊN GITHUB

### B.1. Bảng tổng hợp các dự án chủ lực

| # | Dự án | Repo | Ngôn ngữ | License | Quy mô | Vai trò với đồ án |
|---|---|---|---|---|---|---|
| 1 | **Flagsmith** | `github.com/Flagsmith/flagsmith` | Python/Django + React | BSD-3-Clause | ~6.3k ★ | **Gốc chính** — làm đúng cả feature flag lẫn remote config, stack Python |
| 2 | **Unleash** | `github.com/Unleash/unleash` | TypeScript/Node | Apache-2.0 (open-core) | ~13.4k ★ | Chuẩn tham chiếu về **mô hình activation strategy** và UX dashboard |
| 3 | **GO Feature Flag** | `github.com/thomaspoignant/go-feature-flag` | Go | MIT | ~2k ★ | Gọn nhất, đọc để học **engine đánh giá flag**. License thoáng nhất |
| 4 | **Flipt** | `github.com/flipt-io/flipt` | Go + React | FCL-1.0-MIT (v2) | ~4k ★ | Mô hình **GitOps / flag-as-code**, kiến trúc evaluation sạch |
| 5 | **GrowthBook** | `github.com/growthbook/growthbook` | TypeScript | MIT (core) | ~6k ★ | Tham chiếu phần **thống kê A/B testing** (Bayesian + frequentist) |
| 6 | **Apollo Config** | `github.com/apolloconfig/apollo` | Java/Spring | Apache-2.0 | ~29.8k ★ | Tham chiếu **vế cấu hình**: namespace, release, rollback, grayscale |
| 7 | **OpenFeature** | `github.com/open-feature/spec` | Spec + SDK đa ngôn ngữ | Apache-2.0 | CNCF | **Chuẩn API** cần tuân thủ — dùng lại SDK có sẵn |
| 8 | **flagd** | `github.com/open-feature/flagd` | Go | Apache-2.0 | — | Reference implementation của OpenFeature, đọc để hiểu protocol |
| 9 | **Featurevisor** | `github.com/featurevisor/featurevisor` | TypeScript | MIT | — | Mô hình "không cần server", flag qua CDN datafile |
| 10 | **FeatBit** | `github.com/featbit/featbit` | C#/.NET | MIT | — | Tham chiếu kiến trúc streaming/WebSocket |

### B.2. Ghi chú license — phần này rất quan trọng, đừng bỏ qua

| License | Nghĩa là gì với nhóm | Kết luận |
|---|---|---|
| **MIT** (GO Feature Flag, GrowthBook core, Featurevisor) | Tự do fork, sửa, phân phối. Chỉ cần giữ notice bản quyền | An toàn tuyệt đối |
| **BSD-3-Clause** (Flagsmith) | Tương tự MIT, thêm điều khoản không dùng tên tác giả để quảng bá | An toàn |
| **Apache-2.0** (Unleash core, Apollo, OpenFeature) | Tự do, có điều khoản cấp phép sáng chế. Phải ghi rõ các file đã sửa | An toàn, nhưng nhớ ghi `NOTICE` |
| **FCL-1.0-MIT** (Flipt v2) | Fair Core License — dùng được, sửa được, self-host được, nhưng **cấm dùng để cạnh tranh thương mại với Flipt**; sau 2 năm chuyển thành MIT | Đồ án học thuật thì hợp lệ, nhưng nếu thương mại hóa về sau thì vướng → **chỉ nên đọc tham chiếu, không fork** |

**Cảnh báo mô hình open-core:** Unleash và Flagsmith đều theo mô hình open-core — phần lõi mở, nhưng các tính năng quản trị doanh nghiệp (RBAC nâng cao, SSO/SAML, change request, audit log đầy đủ) nằm ở bản Enterprise trả phí. Đây **vừa là hạn chế của họ, vừa là cơ hội của nhóm**: những tính năng đó chính là chỗ nhóm tự làm và ghi điểm "đóng góp mới".

### B.3. Nhận định từng repo

**Flagsmith** — `https://github.com/Flagsmith/flagsmith`
Điểm mạnh với đồ án này: đây là repo duy nhất trong nhóm dẫn đầu tự định vị là "Feature Flag **và Remote Config**" — trùng khớp 100% với tên đề tài. Backend Django/Python, frontend React. Chạy thử chỉ bằng một lệnh:
```bash
curl -o docker-compose.yml https://raw.githubusercontent.com/Flagsmith/flagsmith/main/docker-compose.yml
docker compose -f docker-compose.yml up
```
Hạn chế: codebase Django 8 năm tuổi, gần 6.000 commit, nhiều lớp abstraction lịch sử. Fork rồi sửa sẽ tốn 3–4 tuần chỉ để hiểu code.

**Unleash** — `https://github.com/Unleash/unleash`
Mô hình "activation strategy" của Unleash là chuẩn mực trong ngành: mỗi flag có nhiều strategy (gradualRolloutUserId, userWithId, flexibleRollout, remoteAddress…), flag bật khi **bất kỳ** strategy nào trả về true. Đây là design pattern đáng học và đáng trích dẫn trong báo cáo. Chạy thử:
```bash
git clone https://github.com/Unleash/unleash.git && cd unleash && docker compose up -d
# http://localhost:4242 — admin / unleash4all
```
Hạn chế: monorepo TypeScript rất lớn, không phù hợp làm gốc cho đồ án sinh viên.

**GO Feature Flag** — `https://github.com/thomaspoignant/go-feature-flag`
Đây là repo **đáng đọc nhất** để học kiến trúc. Không cần database — nạp file cấu hình flag (YAML/JSON/TOML) vào bộ nhớ, hỗ trợ nhiều nguồn cấu hình (file, HTTP, GitHub, GitLab, S3, Google Storage, ConfigMap, MongoDB, PostgreSQL, Azure Blob…). Có relay proxy để các ngôn ngữ khác gọi qua HTTP. License MIT, code Go gọn gàng — đọc hết engine đánh giá trong 1–2 ngày.
Hạn chế: **không có dashboard quản trị runtime** — quản lý theo kiểu GitOps. Chính chỗ thiếu này là phần nhóm sẽ bổ sung.

**Flipt v2** — `https://github.com/flipt-io/flipt`
Đã chuyển hẳn sang Git-native: lưu trạng thái flag trong Git repo, bỏ phụ thuộc database mà v1 yêu cầu. Có multi-environment map theo branch, SSE để đẩy cập nhật realtime, merge proposal kèm code review. Ý tưởng "environment = Git branch" rất hay để trích dẫn. Nhưng vướng license FCL → **chỉ đọc, không fork**.

**Apollo Config** — `https://github.com/apolloconfig/apollo`
Đây là tham chiếu cho **vế thứ hai của đề tài**. Hệ thống quản lý cấu hình của Ctrip, Apache-2.0, ~29.8k sao, dùng thật trong môi trường microservice quy mô lớn. Các khái niệm cần học và bê nguyên vào thiết kế: **App → Cluster → Namespace → Item**, cơ chế **publish/rollback theo release**, **grayscale release** (phát hành xám cho một nhóm instance), **long polling** để client nhận thay đổi gần như tức thời, và mô hình phân quyền/duyệt thay đổi.

**OpenFeature** — `https://github.com/open-feature/spec`
Chuẩn của CNCF cho API feature flagging. **Đây là quyết định kiến trúc quan trọng nhất của cả đồ án.** Nếu backend của nhóm expose API tương thích OpenFeature thì:
- Không phải tự viết SDK cho từng ngôn ngữ — dùng SDK có sẵn của Go, Java, Python, .NET, Node, PHP, Ruby, Swift, Kotlin, Web.
- Có luận điểm học thuật mạnh khi bảo vệ: "hệ thống tuân thủ chuẩn mở của CNCF, tránh vendor lock-in".
- Có bộ test tương thích sẵn để chứng minh tính đúng đắn.

---

## PHẦN C. CHIẾN LƯỢC CHỌN "GỐC" ĐỂ PHÁT TRIỂN

### C.1. Ba con đường và đánh giá thẳng thắn

| | **Con đường 1: Fork nguyên Flagsmith** | **Con đường 2: Viết lại từ đầu 100%** | **Con đường 3: Lai — KHUYẾN NGHỊ** |
|---|---|---|---|
| Cách làm | Clone Flagsmith, sửa và thêm tính năng | Không nhìn repo nào, tự thiết kế | Tự viết lõi, nhưng **bê thiết kế** từ 4 repo + tuân thủ chuẩn OpenFeature |
| Thời gian hiểu code | 3–4 tuần | 0 | 1 tuần đọc tham chiếu |
| Rủi ro bảo vệ | **Cao** — hội đồng hỏi "phần nào là của em?" rất khó trả lời | Thấp | Thấp |
| Chất lượng thiết kế | Cao (kế thừa) | **Rủi ro** — dễ thiết kế sai mô hình dữ liệu | Cao |
| Khối lượng code tự viết | Ít | Rất nhiều | Vừa đủ |
| Điểm đóng góp mới | Khó chứng minh | Dễ nhưng có thể ngây thơ | Rõ ràng, có đối chứng |

### C.2. Khuyến nghị dứt khoát: chọn Con đường 3

**Lý do:** đồ án tốt nghiệp/chuyên ngành chấm trên *phần nhóm thực sự làm ra*, không chấm trên số dòng code. Fork một repo 6.000 commit rồi sửa vài chỗ sẽ rơi vào tình huống tệ nhất khi bảo vệ. Ngược lại, viết mù từ đầu thì 80% khả năng thiết kế sai mô hình dữ liệu ở tuần 3 và phải làm lại.

**Cách làm cụ thể của Con đường 3:**

1. **Tuần 1 — Giải phẫu tham chiếu.** Chạy thật Flagsmith + Unleash bằng Docker. Đọc code engine đánh giá của GO Feature Flag. Đọc tài liệu Apollo về namespace/release. Viết một báo cáo khảo sát 8–10 trang (đây chính là Chương 2 của báo cáo cuối kỳ, làm sớm được luôn).
2. **Tuần 1 — Chốt hợp đồng API.** Lấy chuẩn OpenFeature làm khuôn cho API đánh giá. Đây là phần "kế thừa" hợp pháp và đáng khoe nhất.
3. **Tuần 2 trở đi — Tự viết** backend, engine, dashboard, SDK theo thiết kế đã chốt.
4. **Phần được phép sao chép trực tiếp:** lược đồ CSDL (có điều chỉnh), thuật toán băm để chia phần trăm, danh sách toán tử so khớp, cấu trúc JSON của rule. Đây là *kiến thức miền*, không phải sao chép code. Ghi rõ nguồn trong báo cáo.

### C.3. Các repo cần clone về máy trong tuần 1

```bash
mkdir -p ~/research/ff && cd ~/research/ff

# 1. Gốc tham chiếu chính — cả flag lẫn remote config, stack Python
git clone --depth 1 https://github.com/Flagsmith/flagsmith.git

# 2. Chuẩn mực về activation strategy và UX
git clone --depth 1 https://github.com/Unleash/unleash.git

# 3. Engine đánh giá gọn nhất, MIT — đọc kỹ nhất
git clone --depth 1 https://github.com/thomaspoignant/go-feature-flag.git

# 4. Chuẩn OpenFeature — BẮT BUỘC đọc
git clone --depth 1 https://github.com/open-feature/spec.git
git clone --depth 1 https://github.com/open-feature/flagd.git

# 5. Tham chiếu vế cấu hình
git clone --depth 1 https://github.com/apolloconfig/apollo.git

# 6. Chỉ đọc, không fork (license FCL)
git clone --depth 1 https://github.com/flipt-io/flipt.git

# 7. Danh mục tổng hợp
git clone --depth 1 https://github.com/andrewdmaclean/awesome-feature-flag-management.git
```

### C.4. Đọc cái gì trong mỗi repo (tiết kiệm thời gian)

| Repo | Thư mục/file cần đọc | Mục tiêu rút ra |
|---|---|---|
| `go-feature-flag` | `internal/flag/`, `internal/flagv1/`, `model/` | Cấu trúc rule, cách tính percentage, reason code |
| `flagsmith` | `api/features/models.py`, `api/environments/`, `api/segments/` | Lược đồ CSDL cho flag/segment/environment |
| `unleash` | `src/lib/features/`, `docs/reference/activation-strategies` | Mô hình strategy, kiến trúc project/environment |
| `spec` (OpenFeature) | `specification/sections/` | Hợp đồng API, reason code, error code |
| `flagd` | `core/pkg/eval/` | Cách hiện thực hóa spec thành HTTP/gRPC |
| `apollo` | `docs/` (design), `apollo-portal`, `apollo-configservice` | Namespace, release, rollback, grayscale, long polling |

---

## PHẦN D. PHẠM VI HỆ THỐNG (SCOPE)

Đặt tên hệ thống, ví dụ: **FlagOps** — Nền tảng quản trị Feature Flag và Cấu hình ứng dụng.

### D.1. TRONG phạm vi — Bắt buộc (MUST)

**M1. Quản trị tổ chức**
- Đăng ký / đăng nhập, JWT + refresh token
- Organization → Project → Environment (dev/staging/prod)
- Mời thành viên, phân vai trò: `OWNER`, `ADMIN`, `DEVELOPER`, `VIEWER`
- Quản lý API key theo môi trường (server-side key và client-side key tách biệt)

**M2. Quản trị Feature Flag**
- CRUD flag: `key` (bất biến), tên, mô tả, tag, loại (`BOOLEAN` / `STRING` / `NUMBER` / `JSON`)
- Đánh dấu flag tạm thời (temporary) hay vĩnh viễn (permanent)
- Cấu hình độc lập theo môi trường: bật/tắt, variation mặc định
- Multivariate: nhiều variation, mỗi variation có giá trị riêng
- Archive / khôi phục flag

**M3. Targeting & Rollout**
- Segment: điều kiện theo thuộc tính (`==`, `!=`, `>`, `<`, `>=`, `<=`, `IN`, `NOT IN`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `MATCHES_REGEX`, `SEMVER_GT`, `SEMVER_LT`)
- Ghép điều kiện bằng AND trong một nhóm, OR giữa các nhóm
- Targeting rule có thứ tự ưu tiên, luật khớp đầu tiên thắng
- Percentage rollout **ổn định** theo khóa băm (sticky bucketing)
- Danh sách override cá nhân (bật cứng cho user cụ thể)

**M4. Đánh giá flag (Evaluation)**
- API đánh giá một flag và đánh giá toàn bộ flag
- Trả về đầy đủ: `value`, `variant`, `reason`, `flagMetadata`
- Tương thích chuẩn OpenFeature
- Chế độ đánh giá từ xa (remote) và đánh giá tại chỗ (in-process, tải toàn bộ ruleset về SDK)

**M5. Quản trị cấu hình ứng dụng**
- Namespace theo project + environment
- Config item: `key`, `value`, kiểu dữ liệu, mô tả, cờ `is_secret`
- Version hóa: mỗi lần publish tạo một **Release** bất biến, có số thứ tự
- So sánh diff giữa hai release
- Rollback về release bất kỳ
- Mã hóa giá trị bí mật (AES-256-GCM)
- Validate giá trị bằng JSON Schema trước khi publish

**M6. Phân phối cập nhật**
- SDK polling có `ETag` / `If-None-Match` để tiết kiệm băng thông
- Kênh đẩy realtime bằng SSE (Server-Sent Events)
- Cache nhiều tầng: SDK in-memory → Redis → PostgreSQL

**M7. Audit & An toàn**
- Audit log ghi đầy đủ: ai, làm gì, lúc nào, giá trị trước/sau, IP
- Không xóa cứng dữ liệu quan trọng (soft delete)
- Rate limit API đánh giá

**M8. Dashboard web**
- Danh sách/chi tiết flag, bật tắt nhanh
- Trình soạn rule trực quan (không bắt người dùng viết JSON)
- Trình mô phỏng đánh giá: nhập context giả lập → xem kết quả và **lý do**
- Trình quản lý cấu hình có diff và rollback
- Trang audit log có lọc

**M9. SDK**
- Python SDK (server-side)
- JavaScript/TypeScript SDK (client-side)
- OpenFeature Provider cho cả hai

### D.2. TRONG phạm vi — Nên có (SHOULD) — đây là phần ăn điểm

**S1. Change Request (quy trình duyệt thay đổi).** Trên môi trường production, mọi thay đổi phải qua đề xuất → người khác duyệt → áp dụng. Nguyên tắc bốn mắt. *Unleash và Flagsmith đều tính phí tính năng này.*

**S2. Flag Lifecycle & phát hiện flag chết.** Theo dõi `last_evaluated_at`, tuổi flag, tỉ lệ rollout. Dashboard "nợ kỹ thuật flag" liệt kê flag đã 100% rollout quá 30 ngày → đề xuất dọn dẹp.

**S3. Scheduled change.** Hẹn giờ bật/tắt flag (ví dụ bật khuyến mãi lúc 00:00).

**S4. Analytics đánh giá.** Biểu đồ số lần đánh giá theo variation, theo thời gian.

**S5. Relay Proxy / Edge.** Một service nhẹ đặt gần ứng dụng, cache ruleset, giảm tải cho core.

### D.3. NGOÀI phạm vi — Ghi rõ trong báo cáo để tránh bị hỏi

- Phân tích thống kê A/B testing đầy đủ (Bayesian, p-value, độ tin cậy) — chỉ thu thập dữ liệu thô, không tính toán suy luận
- SSO/SAML doanh nghiệp
- Tích hợp data warehouse
- Mobile SDK native (iOS/Android)
- Multi-region / replication địa lý

---

## PHẦN E. KIẾN TRÚC HỆ THỐNG

### E.1. Sơ đồ ngữ cảnh (C4 Level 1)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Product Mgr  │     │  Developer   │     │   SRE/Ops    │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            ▼
                  ┌───────────────────┐
                  │     FlagOps       │
                  │  (Hệ thống của    │◄──── Ứng dụng khách
                  │   nhóm xây dựng)  │      (qua SDK)
                  └─────────┬─────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        PostgreSQL       Redis      OpenTelemetry
```

### E.2. Sơ đồ container (C4 Level 2)

```
┌─────────────────────────────────────────────────────────────────┐
│                         TRÌNH DUYỆT                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Dashboard SPA — React 18 + TypeScript + Vite             │  │
│  └───────────────────────────┬───────────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────────┘
                               │ HTTPS / JWT
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLAGOPS CORE API (FastAPI)                    │
│                                                                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐  │
│  │   Auth &   │ │   Flag     │ │  Config    │ │  Audit &     │  │
│  │   RBAC     │ │ Management │ │ Management │ │ ChangeReq    │  │
│  └────────────┘ └────────────┘ └────────────┘ └──────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │          EVALUATION ENGINE (thuần, không I/O)             │  │
│  │  Segment Matcher · Rule Resolver · Bucketing (Murmur3)    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────┐ ┌────────────┐ ┌──────────────────────────────┐ │
│  │ Eval API   │ │  SSE Hub   │ │  Scheduler (APScheduler)     │ │
│  │ (public)   │ │ (realtime) │ │  hẹn giờ + phát hiện stale   │ │
│  └────────────┘ └────────────┘ └──────────────────────────────┘ │
└──────┬────────────────────┬──────────────────────┬──────────────┘
       │                    │                      │
       ▼                    ▼                      ▼
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ PostgreSQL  │    │  Redis 7        │    │ OTel Collector  │
│ Nguồn sự    │    │ Cache ruleset   │    │ → Prometheus    │
│ thật        │    │ Pub/Sub         │    │ → Grafana       │
│ JSONB rules │    │ Rate limit      │    │ → Jaeger        │
└─────────────┘    └─────────────────┘    └─────────────────┘
       ▲
       │  (ghi bất đồng bộ, batch)
┌──────┴──────────────┐
│ Evaluation Events   │  ← phục vụ analytics và phát hiện flag chết
└─────────────────────┘

        ┌──────────────────────────────────────┐
        │  ỨNG DỤNG KHÁCH                      │
        │  ┌────────────────────────────────┐  │
        │  │ FlagOps SDK (Python / JS)      │  │
        │  │  ├─ Cache in-memory            │  │
        │  │  ├─ Polling (ETag)             │  │
        │  │  ├─ SSE subscriber             │  │
        │  │  └─ OpenFeature Provider       │  │
        │  └────────────────────────────────┘  │
        └──────────────────────────────────────┘
```

### E.3. Nguyên tắc kiến trúc bắt buộc tuân thủ

1. **Evaluation Engine phải là hàm thuần (pure function).**
   `evaluate(ruleset, context) → result`. Không truy vấn CSDL, không gọi mạng, không đọc đồng hồ hệ thống bên trong. Nhờ vậy engine dùng lại được ở cả server, relay proxy và SDK in-process, đồng thời unit test cực kỳ dễ. **Đây là quyết định thiết kế quan trọng nhất — đừng làm sai.**

2. **Tách hai đường đọc/ghi.** Đường quản trị (dashboard, ghi, có JWT, ít lưu lượng) và đường đánh giá (SDK, đọc, dùng API key, lưu lượng cực lớn) phải tách router, tách rate limit, tách cache. Có thể tách thành hai process khi triển khai.

3. **Cache có phân tầng và có invalidation rõ ràng.**
   Ghi vào PostgreSQL → tăng `ruleset_version` của environment → publish message lên Redis Pub/Sub → SSE Hub đẩy sự kiện xuống SDK → SDK fetch ruleset mới.

4. **Fail-safe, không bao giờ fail-closed sai.** Nếu SDK không kết nối được, phải trả về giá trị mặc định do lập trình viên truyền vào, không được ném exception làm sập ứng dụng khách. Ghi rõ nguyên tắc này trong báo cáo.

5. **Bất biến hóa lịch sử.** Release cấu hình và audit log chỉ thêm, không sửa, không xóa.

---

## PHẦN F. MÔ HÌNH DỮ LIỆU CHI TIẾT

### F.1. Sơ đồ quan hệ tổng quát

```
organization ──< project ──< environment ──< api_key
                    │            │
                    │            ├──< flag_environment_setting >── flag
                    │            ├──< targeting_rule
                    │            ├──< config_namespace ──< config_item
                    │            │                    └──< config_release
                    │            └──< evaluation_event
                    │
                    ├──< flag ──< variation
                    ├──< segment ──< segment_condition
                    └──< membership >── user

audit_log, change_request : tham chiếu chéo toàn hệ thống
```

### F.2. Đặc tả bảng

**`organization`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(120) | |
| slug | VARCHAR(60) UNIQUE | dùng trong URL |
| created_at, updated_at | TIMESTAMPTZ | |

**`user`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| email | CITEXT UNIQUE | |
| password_hash | TEXT | Argon2id |
| full_name | VARCHAR(120) | |
| is_active | BOOLEAN | |
| last_login_at | TIMESTAMPTZ | |

**`membership`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| user_id | FK user | |
| organization_id | FK organization | |
| role | ENUM | OWNER / ADMIN / DEVELOPER / VIEWER |
| UNIQUE(user_id, organization_id) | | |

**`project`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| organization_id | FK | |
| name, slug | VARCHAR | |
| default_stale_days | INT | mặc định 30, phục vụ phát hiện flag chết |

**`environment`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| project_id | FK | |
| name | VARCHAR(60) | development / staging / production |
| key | VARCHAR(60) | |
| is_production | BOOLEAN | quyết định có bắt buộc change request không |
| ruleset_version | BIGINT | tăng mỗi khi có thay đổi → dùng cho ETag |
| UNIQUE(project_id, key) | | |

**`api_key`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| environment_id | FK | |
| name | VARCHAR | |
| key_hash | TEXT | **chỉ lưu hash SHA-256, không lưu khóa gốc** |
| key_prefix | VARCHAR(12) | hiển thị `fo_srv_a1b2…` để nhận diện |
| scope | ENUM | SERVER / CLIENT |
| expires_at | TIMESTAMPTZ NULL | |
| revoked_at | TIMESTAMPTZ NULL | |

> Khóa `CLIENT` bị lộ ra trình duyệt nên chỉ được trả về flag đã đánh dấu `is_client_visible = true`. Đây là chi tiết bảo mật hội đồng rất hay hỏi.

**`flag`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| project_id | FK | |
| key | VARCHAR(160) | **bất biến sau khi tạo**, regex `^[a-zA-Z0-9._-]+$` |
| name, description | | |
| type | ENUM | BOOLEAN / STRING / NUMBER / JSON |
| toggle_kind | ENUM | RELEASE / EXPERIMENT / OPS / PERMISSION |
| is_temporary | BOOLEAN | |
| is_client_visible | BOOLEAN | |
| tags | TEXT[] | |
| archived_at | TIMESTAMPTZ NULL | |
| created_by | FK user | |
| UNIQUE(project_id, key) | | |

**`variation`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| flag_id | FK | |
| key | VARCHAR(80) | `on`, `off`, `control`, `variant_a`… |
| value | JSONB | giá trị thực tế, kiểu tùy `flag.type` |
| name, description | | |
| UNIQUE(flag_id, key) | | |

**`flag_environment_setting`** — quan trọng nhất
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| flag_id | FK | |
| environment_id | FK | |
| enabled | BOOLEAN | công tắc tổng |
| default_variation_id | FK variation | trả về khi không rule nào khớp |
| off_variation_id | FK variation | trả về khi `enabled = false` |
| bucketing_key | VARCHAR(60) | thuộc tính dùng để băm, mặc định `userId` |
| last_evaluated_at | TIMESTAMPTZ | phục vụ phát hiện flag chết |
| UNIQUE(flag_id, environment_id) | | |

**`segment`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| project_id | FK | |
| key, name, description | | |
| conditions | JSONB | cây điều kiện (xem F.3) |

**`targeting_rule`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| flag_environment_setting_id | FK | |
| priority | INT | thứ tự đánh giá, nhỏ hơn chạy trước |
| description | VARCHAR | |
| segment_id | FK segment NULL | dùng segment có sẵn |
| conditions | JSONB NULL | hoặc điều kiện viết trực tiếp |
| distribution | JSONB | `[{"variation_id": "...", "weight": 30}, ...]`, tổng = 100 |
| UNIQUE(flag_environment_setting_id, priority) | | |

**`individual_override`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| flag_environment_setting_id | FK | |
| context_key | VARCHAR(200) | giá trị `userId` cụ thể |
| variation_id | FK | |

**`config_namespace`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| environment_id | FK | |
| name | VARCHAR(120) | `application`, `payment-service`… |
| format | ENUM | PROPERTIES / JSON / YAML |
| current_release_id | FK config_release NULL | |
| UNIQUE(environment_id, name) | | |

**`config_item`** — bản nháp đang chỉnh sửa
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| namespace_id | FK | |
| key | VARCHAR(200) | |
| value | TEXT | đã mã hóa nếu `is_secret` |
| value_type | ENUM | STRING / INT / FLOAT / BOOL / JSON |
| is_secret | BOOLEAN | |
| json_schema | JSONB NULL | validate trước khi publish |
| comment | TEXT | |
| UNIQUE(namespace_id, key) | | |

**`config_release`** — bất biến
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| namespace_id | FK | |
| version | INT | tăng dần trong namespace |
| snapshot | JSONB | **ảnh chụp toàn bộ key-value tại thời điểm publish** |
| comment | TEXT | |
| released_by | FK user | |
| released_at | TIMESTAMPTZ | |
| is_rollback_of | FK config_release NULL | |
| UNIQUE(namespace_id, version) | | |

> Lưu **snapshot toàn bộ** chứ không lưu diff. Rollback khi đó chỉ là tạo release mới với snapshot cũ — an toàn, đơn giản, không bao giờ sai. Diff tính động khi hiển thị.

**`audit_log`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | BIGSERIAL PK | |
| organization_id, project_id, environment_id | FK NULL | |
| actor_id | FK user NULL | NULL nếu do hệ thống/scheduler |
| action | VARCHAR(80) | `flag.toggled`, `config.released`, `rule.updated`… |
| entity_type, entity_id | | |
| before, after | JSONB | |
| ip_address | INET | |
| user_agent | TEXT | |
| created_at | TIMESTAMPTZ | **index BRIN theo thời gian** |

**`change_request`**
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | UUID PK | |
| environment_id | FK | |
| title, description | | |
| payload | JSONB | tập thay đổi chờ áp dụng |
| status | ENUM | DRAFT / PENDING / APPROVED / REJECTED / APPLIED / CANCELLED |
| requested_by, reviewed_by | FK user | |
| scheduled_at | TIMESTAMPTZ NULL | hẹn giờ áp dụng |
| applied_at | TIMESTAMPTZ NULL | |

**`evaluation_event`** — bảng lớn, cần phân vùng
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | BIGSERIAL | |
| environment_id, flag_id, variation_id | FK | |
| reason | VARCHAR(30) | |
| context_key_hash | VARCHAR(64) | **hash, không lưu userId gốc** — bảo vệ dữ liệu cá nhân |
| created_at | TIMESTAMPTZ | PARTITION BY RANGE theo ngày |

### F.3. Cấu trúc JSONB của điều kiện

```json
{
  "op": "AND",
  "children": [
    { "attribute": "country", "operator": "IN", "value": ["VN", "TH"] },
    {
      "op": "OR",
      "children": [
        { "attribute": "plan", "operator": "EQ", "value": "premium" },
        { "attribute": "appVersion", "operator": "SEMVER_GTE", "value": "3.2.0" }
      ]
    }
  ]
}
```

Cấu trúc đệ quy, cho phép lồng nhiều tầng. Viết parser bằng đệ quy, độ sâu giới hạn 5 tầng để tránh DoS.

### F.4. Index bắt buộc

```sql
CREATE INDEX idx_fes_env_flag       ON flag_environment_setting(environment_id, flag_id);
CREATE INDEX idx_rule_fes_priority  ON targeting_rule(flag_environment_setting_id, priority);
CREATE INDEX idx_flag_project_key   ON flag(project_id, key) WHERE archived_at IS NULL;
CREATE INDEX idx_audit_created_brin ON audit_log USING BRIN(created_at);
CREATE INDEX idx_audit_entity       ON audit_log(entity_type, entity_id);
CREATE INDEX idx_apikey_hash        ON api_key(key_hash) WHERE revoked_at IS NULL;
CREATE INDEX idx_segment_cond_gin   ON segment USING GIN(conditions);
```

---

## PHẦN G. THUẬT TOÁN ĐÁNH GIÁ FLAG

Đây là **trái tim của đồ án**. Phần này phải viết kỹ trong báo cáo và phải test rất chắc.

### G.1. Thuật toán tổng quát

```
HÀM evaluate(flag_setting, rules, overrides, context, default_value):

  1. NẾU flag không tồn tại trong ruleset:
       TRẢ VỀ (default_value, reason = "ERROR", code = "FLAG_NOT_FOUND")

  2. NẾU flag_setting.enabled == false:
       TRẢ VỀ (off_variation.value, reason = "DISABLED")

  3. // Override cá nhân — ưu tiên cao nhất
     NẾU tồn tại override khớp context[bucketing_key]:
       TRẢ VỀ (override.variation.value, reason = "TARGETING_MATCH",
               metadata = {matched: "individual_override"})

  4. // Duyệt targeting rule theo priority tăng dần
     VỚI MỖI rule TRONG rules ĐÃ SẮP XẾP THEO priority:
       NẾU matchConditions(rule, context) == true:
           // Đã khớp luật — xác định variation
           NẾU rule.distribution có đúng 1 phần tử weight = 100:
               TRẢ VỀ (variation.value, reason = "TARGETING_MATCH")
           NGƯỢC LẠI:
               variation = bucket(context, flag.key, rule.id, rule.distribution)
               TRẢ VỀ (variation.value, reason = "SPLIT")

  5. // Không luật nào khớp
     TRẢ VỀ (default_variation.value, reason = "DEFAULT")
```

**Nguyên tắc bất di bất dịch:** luật khớp **đầu tiên** thắng và dừng ngay. Không duyệt tiếp. Nếu duyệt tiếp thì thứ tự ưu tiên trở nên vô nghĩa và kết quả không xác định.

### G.2. Thuật toán chia phần trăm ổn định (sticky bucketing)

Đây là chỗ nhiều nhóm làm sai. Không được dùng `random()`. Không được dùng `hash(userId) % 100`.

```python
import mmh3   # MurmurHash3

def bucket(context_value: str, flag_key: str, rule_id: str,
           distribution: list[dict], seed: int = 0) -> str:
    """
    Trả về variation_id một cách ổn định.
    Cùng bộ (context_value, flag_key, rule_id) luôn cho cùng kết quả.
    """
    # Ghép flag_key và rule_id vào chuỗi băm để các flag khác nhau
    # KHÔNG bị tương quan bucket với nhau.
    hash_input = f"{flag_key}:{rule_id}:{context_value}"

    # MurmurHash3 32-bit, lấy giá trị không dấu
    h = mmh3.hash(hash_input, seed, signed=False)

    # Chuẩn hóa về thang 0..9999 để có độ phân giải 0.01%
    bucket_value = h % 10000

    # Duyệt tích lũy trọng số
    cumulative = 0
    for entry in distribution:
        cumulative += entry["weight"] * 100   # weight tính theo %
        if bucket_value < cumulative:
            return entry["variation_id"]

    # Phòng hờ sai số làm tròn — trả phần tử cuối
    return distribution[-1]["variation_id"]
```

**Tại sao phải ghép `flag_key` vào chuỗi băm:** nếu chỉ băm `userId`, thì user rơi vào phân vị thấp sẽ luôn được chọn ở **mọi** flag có rollout 10%. Nhóm người dùng đó trở thành "chuột bạch vĩnh viễn" cho tất cả tính năng mới — sai lệch thống kê nghiêm trọng. Ghép `flag_key` và `rule_id` làm cho phân bố độc lập giữa các flag. **Điểm này nên viết hẳn một mục trong báo cáo, hội đồng rất thích.**

**Tại sao dùng MurmurHash3 chứ không phải MD5/SHA:** Murmur3 là hash không mật mã, nhanh hơn 5–10 lần, phân bố đều rất tốt, và là lựa chọn mà Unleash, Flagsmith, GO Feature Flag, flagd đều dùng — nên kết quả tương thích chéo được.

**Tại sao chia 10000 chứ không phải 100:** cho phép rollout mịn tới 0.01%, cần thiết khi canary trên hệ thống lưu lượng lớn.

### G.3. Bảng toán tử so khớp

| Toán tử | Kiểu áp dụng | Ghi chú triển khai |
|---|---|---|
| `EQ`, `NEQ` | mọi kiểu | so sánh sau khi ép kiểu về cùng loại |
| `GT`, `GTE`, `LT`, `LTE` | số, ngày | ép về `Decimal` hoặc `datetime` |
| `IN`, `NOT_IN` | chuỗi, số | dùng `set` để O(1) |
| `CONTAINS`, `NOT_CONTAINS` | chuỗi | phân biệt hoa thường tùy cờ |
| `STARTS_WITH`, `ENDS_WITH` | chuỗi | |
| `MATCHES_REGEX` | chuỗi | **bắt buộc timeout 50ms** — chống ReDoS |
| `SEMVER_EQ/GT/GTE/LT/LTE` | chuỗi phiên bản | dùng thư viện `packaging` hoặc `semver` |
| `IS_ONE_OF_SEGMENT` | tham chiếu segment | đệ quy, giới hạn độ sâu 3 |
| `EXISTS`, `NOT_EXISTS` | mọi kiểu | kiểm tra thuộc tính có trong context không |

Xử lý thiếu thuộc tính: nếu `context` không có thuộc tính mà rule yêu cầu → điều kiện đó trả `false` (không ném lỗi). Ghi rõ quy ước này vào tài liệu.

### G.4. Bộ test bắt buộc cho engine

Viết **tối thiểu 60 unit test**, chia nhóm:

1. Flag tắt → luôn trả `off_variation`, reason `DISABLED`
2. Không có rule → trả `default_variation`, reason `DEFAULT`
3. Override cá nhân thắng mọi rule
4. Rule priority 1 khớp thì rule priority 2 không được chạy
5. Từng toán tử: mỗi toán tử ít nhất 3 ca (khớp, không khớp, thiếu thuộc tính)
6. Điều kiện lồng AND/OR ba tầng
7. **Tính ổn định của bucketing**: cùng user gọi 1000 lần → 1000 kết quả giống nhau
8. **Tính đều của phân bố**: 100.000 userId ngẫu nhiên, rollout 50/50 → sai lệch < 1%
9. **Tính độc lập giữa flag**: cùng tập user, hai flag rollout 10% → tập giao nhau xấp xỉ 1%, không phải 10%
10. Thay đổi rollout 10% → 20%: **toàn bộ user ở nhóm 10% cũ phải vẫn nằm trong nhóm 20% mới** (monotonic — cực kỳ quan trọng, đây là bài test mà nhiều sản phẩm thương mại vẫn fail)
11. Regex độc hại → phải timeout chứ không treo
12. Giá trị JSON phức tạp làm variation

Test số 8, 9, 10 nên trình bày bằng biểu đồ trong báo cáo. Đây là phần "thực nghiệm và đánh giá" rất mạnh.

---

## PHẦN H. THIẾT KẾ API

### H.1. Quy ước chung

- Base path quản trị: `/api/v1/...` — xác thực bằng `Authorization: Bearer <JWT>`
- Base path đánh giá: `/eval/v1/...` — xác thực bằng `X-FlagOps-Key: <api_key>`
- Định dạng lỗi thống nhất:
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

### H.2. API quản trị (trích yếu)

| Method | Endpoint | Chức năng |
|---|---|---|
| POST | `/api/v1/auth/register` | Đăng ký |
| POST | `/api/v1/auth/login` | Đăng nhập, trả access + refresh token |
| POST | `/api/v1/auth/refresh` | Làm mới token |
| GET | `/api/v1/organizations/{org}/projects` | Danh sách project |
| POST | `/api/v1/projects/{p}/environments` | Tạo môi trường |
| POST | `/api/v1/environments/{e}/api-keys` | Tạo API key (**trả khóa gốc đúng 1 lần**) |
| GET | `/api/v1/projects/{p}/flags` | Danh sách flag, hỗ trợ lọc theo tag/trạng thái |
| POST | `/api/v1/projects/{p}/flags` | Tạo flag + variations |
| PATCH | `/api/v1/flags/{f}` | Sửa metadata (không cho sửa `key`) |
| PUT | `/api/v1/flags/{f}/environments/{e}` | Bật/tắt, đổi default variation |
| PUT | `/api/v1/flags/{f}/environments/{e}/rules` | Ghi đè toàn bộ tập rule (atomic) |
| POST | `/api/v1/flags/{f}/environments/{e}/simulate` | **Mô phỏng đánh giá** — nhận context, trả kết quả + reason + rule đã khớp |
| GET | `/api/v1/projects/{p}/segments` | Danh sách segment |
| GET | `/api/v1/environments/{e}/namespaces` | Danh sách namespace cấu hình |
| PUT | `/api/v1/namespaces/{n}/items` | Sửa bản nháp cấu hình |
| POST | `/api/v1/namespaces/{n}/releases` | Publish → tạo release mới |
| GET | `/api/v1/namespaces/{n}/releases/{v1}/diff/{v2}` | So sánh hai release |
| POST | `/api/v1/namespaces/{n}/releases/{v}/rollback` | Rollback |
| GET | `/api/v1/environments/{e}/audit-logs` | Audit log, phân trang cursor |
| POST | `/api/v1/environments/{e}/change-requests` | Tạo đề xuất thay đổi |
| POST | `/api/v1/change-requests/{c}/approve` | Duyệt và áp dụng |
| GET | `/api/v1/projects/{p}/flag-health` | **Báo cáo nợ kỹ thuật flag** |

### H.3. API đánh giá (đường nóng, tối ưu hiệu năng)

**Đánh giá một flag**
```http
POST /eval/v1/flags/{flag_key}/evaluate
X-FlagOps-Key: fo_srv_a1b2c3...
Content-Type: application/json

{
  "context": {
    "targetingKey": "user-8891",
    "country": "VN",
    "plan": "premium",
    "appVersion": "3.4.1"
  },
  "defaultValue": false
}
```
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

**Đánh giá tất cả flag (dùng khi khởi tạo client)**
```http
POST /eval/v1/flags/evaluate-all
```

**Tải toàn bộ ruleset để đánh giá tại chỗ**
```http
GET /eval/v1/ruleset
X-FlagOps-Key: fo_srv_...
If-None-Match: "142"
```
Trả `304 Not Modified` nếu chưa đổi — tiết kiệm băng thông rất lớn khi có hàng nghìn instance polling.

**Kênh realtime**
```http
GET /eval/v1/stream
Accept: text/event-stream
```
```
event: ruleset_updated
data: {"environmentId":"...","rulesetVersion":143}

event: heartbeat
data: {}
```
Heartbeat mỗi 25 giây để giữ kết nối qua proxy/load balancer.

**Gửi sự kiện đánh giá (batch, bất đồng bộ)**
```http
POST /eval/v1/events
{"events":[{"flagKey":"...","variant":"on","reason":"SPLIT","ts":1758...}]}
```

### H.4. Chỉ tiêu hiệu năng cần đo và đưa vào báo cáo

| Chỉ tiêu | Mục tiêu |
|---|---|
| Đánh giá in-process trong SDK | p99 < 1 ms |
| `POST /eval/v1/flags/{key}/evaluate` (có cache Redis) | p99 < 30 ms |
| `GET /eval/v1/ruleset` khi trả 304 | p99 < 10 ms |
| Độ trễ lan truyền thay đổi qua SSE | < 2 giây |
| Thông lượng | ≥ 1.500 req/s trên 1 instance (đo bằng k6) |
| API quản trị | p95 < 300 ms |

---

## PHẦN I. SDK VÀ CHUẨN OPENFEATURE

### I.1. Vì sao phải bám OpenFeature

OpenFeature là chuẩn của CNCF, định nghĩa sẵn: khái niệm `Provider`, `EvaluationContext`, `Hook`, tập `reason` (`STATIC`, `DEFAULT`, `TARGETING_MATCH`, `SPLIT`, `CACHED`, `DISABLED`, `UNKNOWN`, `ERROR`) và tập mã lỗi (`FLAG_NOT_FOUND`, `TYPE_MISMATCH`, `PARSE_ERROR`, `PROVIDER_NOT_READY`, `GENERAL`).

Lợi ích cụ thể cho đồ án:
- Nhóm chỉ cần viết **Provider** (vài trăm dòng), phần SDK phức tạp đã có sẵn từ cộng đồng.
- Ứng dụng demo có thể đổi từ FlagOps sang flagd chỉ bằng một dòng cấu hình → **chứng minh được tính không khóa nhà cung cấp**, một luận điểm rất mạnh khi bảo vệ.
- Có sẵn bộ test tuân thủ chuẩn để chứng minh tính đúng đắn.

### I.2. Thiết kế SDK

**SDK Python (server-side)**
```python
from flagops import FlagOpsClient

client = FlagOpsClient(
    api_key="fo_srv_...",
    base_url="https://flagops.example.com",
    mode="in_process",        # tải ruleset về, đánh giá tại chỗ
    polling_interval=30,       # giây, dùng ETag
    enable_streaming=True,     # SSE để nhận cập nhật tức thì
    default_timeout=2.0,
)

if client.is_enabled("checkout-v2",
                     context={"targetingKey": user.id, "country": user.country},
                     default=False):
    render_new_checkout()

color = client.get_string("banner-color", context=ctx, default="blue")
cfg   = client.get_config("payment-service")   # vế cấu hình
```

**Vòng đời SDK**
```
init → tải ruleset lần đầu (chặn, có timeout) → sẵn sàng
  ├─ luồng nền: polling mỗi N giây với ETag
  ├─ luồng nền: SSE subscriber, có cập nhật thì fetch ngay
  ├─ luồng nền: gom sự kiện đánh giá, flush theo batch mỗi 10s
  └─ close() → flush nốt sự kiện, đóng kết nối
```

**Quy tắc an toàn bắt buộc:**
- Nếu chưa tải được ruleset → trả `default` do lập trình viên truyền vào, reason `ERROR`, ghi log cảnh báo, **không ném exception**
- Nếu mất kết nối → tiếp tục dùng ruleset cache cuối cùng, **không được tắt hết flag**
- Kết nối lại theo exponential backoff kèm jitter: 1s, 2s, 4s, 8s… tối đa 60s

**OpenFeature Provider**
```python
from openfeature import api
from flagops.openfeature import FlagOpsProvider

api.set_provider(FlagOpsProvider(api_key="fo_srv_..."))
client = api.get_client()
enabled = client.get_boolean_value("checkout-v2", False, ctx)
```

**SDK JavaScript (client-side)** — cơ chế tương tự nhưng dùng `CLIENT` key, chỉ nhận flag có `is_client_visible = true`, ruleset đã được server đánh giá sẵn (bootstrapped) để không lộ logic targeting ra trình duyệt. **Đây là chi tiết bảo mật quan trọng cần nêu trong báo cáo.**

---

## PHẦN J. MODULE QUẢN TRỊ CẤU HÌNH

Học trực tiếp từ Apollo Config.

### J.1. Mô hình khái niệm

```
Project  →  Environment  →  Namespace  →  Item (key/value)
                               │
                               └─→  Release (v1, v2, v3... bất biến)
```

- **Namespace** tách cấu hình theo service hoặc theo nhóm chức năng. Namespace `application` là mặc định.
- Sửa `Item` chỉ ảnh hưởng **bản nháp**. Ứng dụng khách không thấy gì cả.
- **Publish** đóng băng bản nháp thành `Release` có số version, lúc đó client mới nhận được.

Việc tách nháp/phát hành này là điểm khác biệt cốt lõi so với "sửa file .env" — và là thứ làm cho hệ thống an toàn. Nêu rõ trong báo cáo.

### J.2. Luồng publish

```
1. Người dùng sửa các item trong namespace  (trạng thái: DRAFT, có badge "có thay đổi chưa phát hành")
2. Bấm "Xem thay đổi" → hiển thị diff so với release hiện tại
3. Validate:
   - Mỗi item có json_schema thì kiểm tra giá trị theo schema
   - Kiểm tra kiểu dữ liệu khớp value_type
   - Cảnh báo nếu xóa key đang được tham chiếu
4. NẾU environment.is_production == true:
       tạo Change Request → chờ duyệt
   NGƯỢC LẠI:
       publish ngay
5. Publish:
   - Chụp snapshot toàn bộ key-value
   - Tạo config_release với version = max(version) + 1
   - Cập nhật namespace.current_release_id
   - Tăng environment.ruleset_version
   - Ghi audit_log
   - Publish message Redis → SSE đẩy xuống client
```

### J.3. Rollback

```
Rollback về version V:
  1. Đọc snapshot của release V
  2. Tạo release MỚI (version = max + 1) với snapshot đó
  3. Đánh dấu is_rollback_of = V
  4. Ghi audit log với action = "config.rolled_back"
```

**Không bao giờ xóa hay sửa release cũ.** Lịch sử là bất biến — nguyên tắc này giống Git, dễ giải thích khi bảo vệ.

### J.4. Xử lý giá trị bí mật

```python
# Mã hóa envelope: mỗi giá trị có DEK riêng, DEK được bọc bằng master key
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt_secret(plaintext: str, master_key: bytes) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(master_key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()
```
- Master key lấy từ biến môi trường, **không bao giờ commit vào Git**
- API trả về giá trị bí mật dưới dạng `••••••` trừ khi người gọi có quyền `ADMIN` trở lên và yêu cầu tường minh
- Audit log ghi lại mọi lần đọc giá trị bí mật
- Snapshot trong release lưu bản đã mã hóa

### J.5. Grayscale release (nâng cao, nếu còn thời gian)

Phát hành cấu hình cho một tập instance nhỏ trước:
```
config_gray_release:
  - release_id
  - target_instance_ids [] hoặc target_percentage
  - status: ACTIVE / PROMOTED / ABANDONED
```
Client gửi kèm `instanceId` khi fetch; server quyết định trả release chính hay release xám. Sau khi theo dõi ổn định thì "promote" thành release chính. Ý tưởng bê nguyên từ Apollo.

---

## PHẦN K. ĐIỂM KHÁC BIỆT HỌC THUẬT

Hội đồng chắc chắn sẽ hỏi: *"Unleash và Flagsmith đã có sẵn, đồ án của em mới ở chỗ nào?"* Phải có câu trả lời chuẩn bị sẵn. Đây là bốn hướng, chọn **2 hướng** làm sâu.

### K.1. Quản trị vòng đời flag và đo nợ kỹ thuật ★ khuyến nghị mạnh nhất

**Vấn đề thật:** flag tích tụ theo thời gian. Flag đã rollout 100% từ 6 tháng trước nhưng code vẫn còn `if (flag)` — nợ kỹ thuật. Unleash tính phí tính năng lifecycle này; Flagsmith gần như không có.

**Nhóm sẽ làm:**
- Máy trạng thái vòng đời: `DRAFT → ACTIVE → ROLLED_OUT → STALE → ARCHIVED`
- Tính **điểm nợ kỹ thuật flag** cho mỗi flag:
  ```
  debt_score = w1·(số ngày kể từ khi tạo / stale_threshold)
             + w2·(1 nếu rollout = 100% liên tục > 30 ngày)
             + w3·(1 nếu là temporary flag quá hạn)
             + w4·(1 nếu không có lần đánh giá nào trong 14 ngày)
  ```
- Dashboard xếp hạng flag theo `debt_score`, có nút "đề nghị dọn dẹp"
- **Code scanner**: một CLI quét repo của ứng dụng, tìm các `flag_key` còn tồn tại trong code nhưng đã `ARCHIVED` trên hệ thống, xuất báo cáo và tạo issue GitHub tự động
- Đánh giá thực nghiệm: chạy scanner trên một repo mở, thống kê số flag chết phát hiện được

Hướng này **có đóng góp rõ ràng, đo được, và giải quyết vấn đề thật**. Đây là hướng nên chọn.

### K.2. Quy trình duyệt thay đổi và an toàn production

Change Request bốn mắt, hẹn giờ áp dụng, và **kiểm tra tác động trước khi áp dụng**: trước khi duyệt, hệ thống mô phỏng thay đổi trên N context mẫu gần đây và báo "thay đổi này sẽ ảnh hưởng ~34% người dùng, chuyển 12.000 user từ `control` sang `variant_a`". Unleash/Flagsmith đều tính phí tính năng duyệt; phần mô phỏng tác động thì gần như không sản phẩm nào có.

### K.3. Hợp nhất Feature Flag và Config Center

Đa số sản phẩm chỉ mạnh một vế. Nhóm xây dựng mô hình dữ liệu và SDK **thống nhất**, cho phép:
- Một flag có thể trả về cả một khối cấu hình JSON (`getConfig` và `getFlag` dùng chung đường truyền)
- Cấu hình cũng targeting được theo segment (ví dụ `payment.timeout_ms = 5000` với user ở VN, `3000` với user ở SG)

Đây chính là cách trả lời sát nhất với tên đề tài. **Nên chọn hướng này làm hướng thứ hai.**

### K.4. Tự động rollback theo chỉ số (nâng cao, rủi ro cao)

Kết nối Prometheus, đặt "guardrail": nếu tỉ lệ lỗi HTTP 5xx của service vượt ngưỡng trong 5 phút sau khi bật flag → tự động tắt flag và báo động. Rất ấn tượng khi demo nhưng phụ thuộc hạ tầng giám sát. **Chỉ làm nếu tuần 13 vẫn đúng tiến độ.**

---

## PHẦN L. CÔNG NGHỆ SỬ DỤNG

### L.1. Stack khuyến nghị

| Tầng | Công nghệ | Lý do chọn |
|---|---|---|
| Backend | **Python 3.12 + FastAPI** | Async sẵn, OpenAPI tự sinh, hiệu năng tốt, phù hợp thế mạnh nhóm |
| ORM | SQLAlchemy 2.0 (async) + Alembic | Migration có version, hỗ trợ JSONB tốt |
| Validate | Pydantic v2 | Validate request/response, sinh schema |
| CSDL | **PostgreSQL 16** | JSONB + GIN index cho rule, partition cho bảng sự kiện |
| Cache & Bus | **Redis 7** | Cache ruleset, Pub/Sub invalidation, rate limit |
| Realtime | `sse-starlette` | SSE nhẹ hơn WebSocket, đủ dùng cho một chiều |
| Hash | `mmh3` | MurmurHash3, tương thích với các nền tảng khác |
| Nền lịch | APScheduler | Hẹn giờ flag, quét stale |
| Frontend | **React 18 + TypeScript + Vite** | |
| UI kit | Tailwind CSS + shadcn/ui | Đẹp nhanh, không tốn thời gian CSS |
| State/Data | TanStack Query + Zustand | Cache server state, tối ưu re-render |
| Form | React Hook Form + Zod | Validate rule builder phức tạp |
| Biểu đồ | Recharts | Analytics |
| Auth | JWT (`python-jose`) + Argon2 (`passlib`) | |
| Observability | OpenTelemetry + Prometheus + Grafana + Jaeger | Phần "phi chức năng" ăn điểm |
| Test BE | pytest, pytest-asyncio, testcontainers, hypothesis | `hypothesis` để property test cho engine |
| Test FE | Vitest + React Testing Library + Playwright | |
| Tải | k6 | Đo thông lượng |
| CI/CD | GitHub Actions | |
| Đóng gói | Docker + Docker Compose | Chấm đồ án phải chạy được bằng 1 lệnh |

### L.2. Nếu nhóm mạnh Node hơn Python

Thay backend bằng **NestJS + TypeScript + Prisma + PostgreSQL**. Lợi ích phụ: dùng chung type giữa backend, frontend và SDK JS. Mọi phần còn lại của kế hoạch này giữ nguyên.

### L.3. Cấu trúc thư mục monorepo

```
flagops/
├── docker-compose.yml
├── docker-compose.dev.yml
├── Makefile                      # make up / make test / make seed
├── README.md
├── docs/
│   ├── 01-srs.md                 # Đặc tả yêu cầu
│   ├── 02-architecture.md        # Kiến trúc + ADR
│   ├── 03-data-model.md
│   ├── 04-api-spec.yaml          # OpenAPI 3.1
│   ├── 05-evaluation-algorithm.md
│   ├── adr/                      # Architecture Decision Records
│   └── diagrams/                 # PlantUML / Mermaid nguồn
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── core/                 # config, security, deps, exceptions
│       ├── models/               # SQLAlchemy models
│       ├── schemas/              # Pydantic schemas
│       ├── api/
│       │   ├── admin/            # đường quản trị
│       │   └── eval/             # đường đánh giá (tách biệt)
│       ├── services/             # business logic
│       ├── engine/               # ★ EVALUATION ENGINE — thuần, không I/O
│       │   ├── evaluator.py
│       │   ├── matcher.py
│       │   ├── bucketing.py
│       │   └── operators.py
│       ├── realtime/             # SSE hub
│       ├── jobs/                 # scheduler
│       └── tests/
├── frontend/
│   ├── package.json
│   └── src/
│       ├── pages/
│       ├── features/             # flags/, config/, segments/, audit/
│       ├── components/
│       └── lib/
├── sdk/
│   ├── python/
│   │   └── flagops/
│   └── javascript/
│       └── src/
├── demo-app/                     # ứng dụng mẫu để demo khi bảo vệ
├── tools/
│   └── flag-scanner/             # CLI quét flag chết (điểm khác biệt K.1)
└── load-tests/
    └── k6/
```

---

## PHẦN M. KẾ HOẠCH 15 TUẦN

Giả định: nhóm 4 người, mỗi người 15–20 giờ/tuần. Sprint 2 tuần, có demo nội bộ cuối mỗi sprint.

### Tuần 1 — Sprint 0: Khảo sát và thiết kế

| Ngày | Công việc | Đầu ra |
|---|---|---|
| T2 | Đọc lại đề bài, chốt phạm vi MUST/SHOULD/OUT | Bảng scope đã ký |
| T2–T3 | Chạy Flagsmith + Unleash bằng Docker, thao tác thử toàn bộ chức năng | Ảnh chụp + ghi chú UX |
| T3–T4 | Đọc code `go-feature-flag` (engine) và spec OpenFeature | Ghi chú kiến trúc |
| T4 | Đọc tài liệu thiết kế Apollo phần namespace/release | Ghi chú |
| T5 | Vẽ ERD, chốt mô hình dữ liệu | `docs/03-data-model.md` |
| T5 | Viết đặc tả API bằng OpenAPI 3.1 | `docs/04-api-spec.yaml` |
| T6 | Dựng repo, Docker Compose, CI khung, pre-commit | Repo chạy `make up` được |
| T7 | Viết báo cáo khảo sát (thành Chương 2 báo cáo) | 8–10 trang |

**Cổng kiểm soát tuần 1:** ERD được duyệt, OpenAPI spec có đủ endpoint chính, `docker compose up` chạy được khung rỗng. Nếu chưa đạt thì **không được sang tuần 2**.

### Tuần 2–3 — Sprint 1: Nền tảng

- Migration Alembic đầy đủ cho toàn bộ bảng ở Phần F
- Auth: đăng ký, đăng nhập, JWT + refresh, Argon2
- CRUD organization / project / environment
- RBAC: decorator kiểm quyền theo vai trò
- API key: sinh, hash, xác thực, thu hồi
- Middleware audit log (ghi tự động mọi thao tác ghi)
- Frontend: layout, routing, trang login, trang danh sách project
- CI: lint (ruff, eslint) + test + build Docker image
- **Demo cuối sprint:** đăng nhập, tạo project, tạo môi trường, tạo API key

### Tuần 4–5 — Sprint 2: Flag và Engine v1

- CRUD flag + variations
- `flag_environment_setting`: bật/tắt theo môi trường
- **Engine v1**: xử lý flag boolean, enabled/disabled, default variation
- API `POST /eval/v1/flags/{key}/evaluate`
- Cache ruleset vào Redis + invalidation qua Pub/Sub
- Frontend: danh sách flag, chi tiết flag, toggle nhanh, chuyển môi trường
- **Test: ≥ 25 unit test cho engine**
- **Demo:** tạo flag, bật ở dev, tắt ở prod, gọi API đánh giá bằng curl thấy khác nhau

### Tuần 6–7 — Sprint 3: Targeting và Rollout

- CRUD segment với trình soạn điều kiện
- Bộ toán tử đầy đủ (Phần G.3)
- Targeting rule có priority, kéo thả đổi thứ tự
- **Thuật toán bucketing MurmurHash3** + phân phối variation
- Individual override
- API `simulate` — mô phỏng đánh giá
- Frontend: rule builder trực quan, trang mô phỏng
- **Test: đủ 60 test, bao gồm test phân bố đều, độc lập và monotonic**
- **Demo:** tạo rule "premium user ở VN → bật", mô phỏng 3 context khác nhau, xem reason

> Đây là sprint khó nhất. Nếu trễ, cắt bớt `SEMVER_*` và `MATCHES_REGEX` để làm sau.

### Tuần 8–9 — Sprint 4: Quản trị cấu hình

- CRUD namespace và config item
- Cơ chế nháp / publish / release
- So sánh diff giữa hai release
- Rollback
- Mã hóa giá trị bí mật
- Validate bằng JSON Schema
- API `GET /eval/v1/config/{namespace}`
- Frontend: bảng cấu hình, badge "chưa phát hành", modal diff, lịch sử release, nút rollback
- **Demo:** sửa cấu hình, xem diff, publish, rollback về version cũ

### Tuần 10–11 — Sprint 5: Phân phối và SDK

- `GET /eval/v1/ruleset` với ETag/304
- SSE hub + heartbeat + Redis Pub/Sub
- **SDK Python**: in-process evaluation, polling, SSE, batch events, fail-safe
- **SDK JavaScript**: client-side, chỉ flag public
- **OpenFeature Provider** cho cả hai
- Ứng dụng demo dùng SDK
- Relay proxy (nếu kịp)
- **Test:** integration test SDK ↔ server bằng testcontainers
- **Demo:** ứng dụng đang chạy, đổi flag trên dashboard, ứng dụng đổi hành vi trong < 2 giây mà không restart

> Đây là màn demo ấn tượng nhất khi bảo vệ. Đầu tư kỹ.

### Tuần 12–13 — Sprint 6: Điểm khác biệt

- Change Request: tạo, duyệt, từ chối, áp dụng, hẹn giờ
- Mô phỏng tác động trước khi duyệt
- Thu thập `evaluation_event` (bảng phân vùng)
- **Vòng đời flag + điểm nợ kỹ thuật + dashboard flag health**
- **CLI `flag-scanner`** quét repo tìm flag chết
- Analytics: biểu đồ đánh giá theo variation
- **Demo:** đề xuất thay đổi trên prod → tài khoản khác duyệt → áp dụng; mở dashboard flag health

### Tuần 14 — Sprint 7: Hoàn thiện

- Load test bằng k6, đo và ghi nhận các chỉ tiêu ở H.4
- Tối ưu query (`EXPLAIN ANALYZE` các truy vấn đường nóng)
- Rà soát bảo mật: OWASP Top 10, SQL injection, XSS, CSRF, rate limit, kiểm tra quyền ở mọi endpoint
- E2E test bằng Playwright cho 5 luồng chính
- Viết `README` đầy đủ, hướng dẫn cài đặt, tài liệu SDK
- Sửa toàn bộ bug P1/P2
- Seed data đẹp phục vụ demo

### Tuần 15 — Báo cáo và bảo vệ

- Hoàn thiện báo cáo (bố cục ở Phần R)
- Làm slide 20–25 trang
- **Quay video demo dự phòng** (phòng khi live demo hỏng — luôn luôn phải có)
- Tập bảo vệ ít nhất 3 lần, bấm giờ
- Chuẩn bị trả lời 20 câu hỏi dự kiến (Phần R.3)

### M.2. Cột mốc và cổng kiểm soát

| Mốc | Thời điểm | Tiêu chí vượt qua |
|---|---|---|
| M0 | Cuối T1 | ERD + OpenAPI duyệt xong, repo chạy |
| M1 | Cuối T3 | Auth + RBAC + audit hoạt động, CI xanh |
| M2 | Cuối T5 | Đánh giá flag boolean end-to-end |
| M3 | Cuối T7 | Targeting + rollout đúng, 60 test xanh |
| M4 | Cuối T9 | Module cấu hình đủ publish/rollback |
| M5 | Cuối T11 | SDK + realtime hoạt động, demo "đổi flag → app đổi" |
| M6 | Cuối T13 | Hai điểm khác biệt hoàn thành |
| M7 | Cuối T14 | Không còn bug P1, có số liệu hiệu năng |
| M8 | Cuối T15 | Báo cáo + slide + video demo sẵn sàng |

**Quy tắc xử lý trễ hạn:** nếu trễ một mốc quá 4 ngày, **cắt scope** (bỏ SHOULD trước), không kéo dài thời gian. Thứ tự cắt: K.4 → Relay proxy → Grayscale release → Analytics → SDK JavaScript → Change Request.

---

## PHẦN N. PHÂN CÔNG NHÓM

### N.1. Nhóm 4 người

| Vai trò | Người | Phụ trách chính | Phụ trách phụ |
|---|---|---|---|
| **BE-1 / Tech Lead** | | Evaluation engine, bucketing, segment matcher, kiến trúc, ADR | Review toàn bộ PR |
| **BE-2** | | Auth, RBAC, module cấu hình, audit, change request | Migration, seed data |
| **FE** | | Toàn bộ dashboard React, rule builder, trang diff, analytics | UX, biểu đồ báo cáo |
| **SDK/DevOps/QA** | | SDK Python + JS, OpenFeature provider, Docker, CI/CD, k6, flag-scanner | Test plan, E2E |

**Người viết engine (BE-1) phải là người vững nhất nhóm.** Engine sai thì cả hệ thống sai và bug rất khó tìm.

### N.2. Nhóm 3 người
Gộp SDK/DevOps/QA vào BE-2. Cắt SDK JavaScript, chỉ làm SDK Python. Cắt K.4.

### N.3. Nhóm 2 người
Cắt mạnh: bỏ Change Request, bỏ analytics, bỏ SDK JS, bỏ grayscale, bỏ relay proxy. Giữ MUST + một điểm khác biệt duy nhất (K.1).

### N.4. Quy tắc làm việc

- **Git flow:** `main` (luôn deploy được) ← `develop` ← `feature/FO-123-ten-tinh-nang`
- **Commit:** Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- **PR:** bắt buộc 1 reviewer, CI phải xanh, không merge PR > 500 dòng thay đổi
- **Họp:** 15 phút, 3 buổi/tuần (T2, T4, T7) — mỗi người trả lời: làm gì rồi, làm gì tiếp, vướng gì
- **Bảng công việc:** GitHub Projects, cột `Backlog / Todo / In Progress / Review / Done`
- **Tài liệu ADR:** mọi quyết định kiến trúc quan trọng ghi một file `docs/adr/NNN-ten-quyet-dinh.md` — đây là thứ hội đồng đánh giá rất cao và hầu như không nhóm nào làm

---

## PHẦN O. KẾ HOẠCH KIỂM THỬ

### O.1. Kim tự tháp kiểm thử

```
            ┌─────────────┐
            │  E2E  (5)   │   Playwright, 5 luồng chính
          ┌─┴─────────────┴─┐
          │ Integration (40)│   testcontainers: API + PostgreSQL + Redis
        ┌─┴─────────────────┴─┐
        │    Unit  (150+)     │   engine 60, services 60, utils 30
        └─────────────────────┘
```

Mục tiêu độ phủ: **engine ≥ 95%**, services ≥ 80%, tổng thể ≥ 75%.

### O.2. Property-based test cho engine (dùng `hypothesis`)

```python
from hypothesis import given, strategies as st

@given(user_id=st.text(min_size=1, max_size=64))
def test_bucketing_on_dinh(user_id):
    """Cùng đầu vào phải cho cùng kết quả, mọi lúc."""
    kq1 = bucket(user_id, "flag-a", "rule-1", DIST_50_50)
    kq2 = bucket(user_id, "flag-a", "rule-1", DIST_50_50)
    assert kq1 == kq2

@given(user_ids=st.lists(st.uuids(), min_size=10000, max_size=10000))
def test_phan_bo_deu(user_ids):
    """Rollout 50/50 phải chia gần đều."""
    ket_qua = [bucket(str(u), "flag-a", "rule-1", DIST_50_50) for u in user_ids]
    ti_le = ket_qua.count("var_a") / len(ket_qua)
    assert 0.48 < ti_le < 0.52

def test_tang_rollout_khong_mat_user():
    """10% → 20%: mọi user ở nhóm 10% cũ vẫn phải ở trong nhóm 20% mới."""
    users = [f"user-{i}" for i in range(20000)]
    nhom_10 = {u for u in users if bucket(u, "f", "r", DIST_10) == "on"}
    nhom_20 = {u for u in users if bucket(u, "f", "r", DIST_20) == "on"}
    assert nhom_10.issubset(nhom_20)   # monotonic
```

Ba bài test này nên đưa vào báo cáo kèm biểu đồ. Chúng chứng minh tính đúng đắn của thuật toán một cách định lượng.

### O.3. Các ca kiểm thử bảo mật bắt buộc

| Ca | Kỳ vọng |
|---|---|
| Dùng API key môi trường `dev` gọi ruleset của `prod` | 403 |
| Dùng `CLIENT` key lấy flag có `is_client_visible = false` | Không trả về flag đó |
| Vai trò `VIEWER` gọi API sửa flag | 403 |
| Người dùng org A truy cập project org B | 404 (không phải 403, tránh lộ sự tồn tại) |
| API key đã thu hồi | 401 |
| Gửi 10.000 req/phút từ một key | 429 sau ngưỡng |
| Regex `(a+)+$` với chuỗi dài | Timeout, không treo server |
| JSONB điều kiện lồng 50 tầng | Từ chối, lỗi 400 |
| SQL injection qua tham số lọc | Bị chặn (ORM tham số hóa) |
| XSS qua tên flag/mô tả | Escape đúng khi render |

### O.4. Kịch bản E2E (Playwright)

1. Đăng ký → tạo org → tạo project → tạo môi trường
2. Tạo flag boolean → bật ở dev → gọi API đánh giá → nhận `true`
3. Tạo segment → tạo targeting rule → mô phỏng với 2 context → thấy 2 kết quả khác nhau
4. Sửa cấu hình → xem diff → publish → rollback → kiểm tra giá trị đã quay lại
5. Tạo change request trên prod → tài khoản khác duyệt → thay đổi được áp dụng → có trong audit log

---

## PHẦN P. DEVOPS & CI/CD

### P.1. Pipeline GitHub Actions

```yaml
name: CI
on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: test }
        options: >-
          --health-cmd pg_isready --health-interval 10s --health-retries 5
      redis:
        image: redis:7
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e "backend[dev]"
      - run: ruff check backend/
      - run: mypy backend/app
      - run: alembic upgrade head
      - run: pytest --cov=app --cov-report=xml --cov-fail-under=75
      - run: pytest backend/app/tests/engine --cov=app.engine --cov-fail-under=95

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "22" }
      - run: npm ci --prefix frontend
      - run: npm run lint --prefix frontend
      - run: npm run typecheck --prefix frontend
      - run: npm run test --prefix frontend
      - run: npm run build --prefix frontend

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install pip-audit && pip-audit -r backend/requirements.txt
      - run: npm audit --prefix frontend --audit-level=high
```

### P.2. Docker Compose (chạy được bằng 1 lệnh)

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: flagops
      POSTGRES_PASSWORD: flagops
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]

  redis:
    image: redis:7-alpine

  api:
    build: ./backend
    depends_on:
      postgres: { condition: service_healthy }
      redis:    { condition: service_started }
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:flagops@postgres/flagops
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY:-dev-only-change-me}
      CONFIG_MASTER_KEY: ${CONFIG_MASTER_KEY:-dev-only-32-bytes-key-change-me!}
    ports: ["8000:8000"]
    command: >
      sh -c "alembic upgrade head &&
             python -m app.seed &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000"

  web:
    build: ./frontend
    ports: ["3000:80"]
    depends_on: [api]

  demo:
    build: ./demo-app
    ports: ["3001:3001"]
    depends_on: [api]

volumes: { pgdata: }
```

Mục tiêu: **giảng viên clone repo, gõ `docker compose up`, sau 2 phút mở `localhost:3000` là dùng được với dữ liệu mẫu sẵn.** Nếu phải làm quá 2 bước là mất điểm.

### P.3. Quan sát hệ thống (Observability)

- OpenTelemetry instrument FastAPI, SQLAlchemy, Redis
- Metric tùy chỉnh cần expose:
  - `flagops_evaluations_total{flag_key, variant, reason}`
  - `flagops_evaluation_duration_seconds` (histogram)
  - `flagops_ruleset_cache_hits_total` / `_misses_total`
  - `flagops_sse_connections_active`
  - `flagops_config_releases_total`
- Grafana dashboard có sẵn trong repo (`grafana/dashboards/*.json`) → **mở ra khi demo rất ấn tượng**

---

## PHẦN Q. RỦI RO VÀ PHƯƠNG ÁN XỬ LÝ

| # | Rủi ro | Khả năng | Tác động | Phòng ngừa | Xử lý khi xảy ra |
|---|---|---|---|---|---|
| R1 | Phình phạm vi — muốn làm bằng Unleash | **Cao** | **Cao** | Chốt scope MUST/SHOULD từ tuần 1, ký xác nhận | Cắt theo thứ tự ở M.2 |
| R2 | Thiết kế sai mô hình dữ liệu, phát hiện ở tuần 6 | Trung bình | **Cao** | Cổng kiểm soát M0, đối chiếu ERD với Flagsmith | Migration Alembic đã có sẵn, sửa sớm còn kịp |
| R3 | Bucketing sai, phân bố lệch | Trung bình | **Cao** | Property test từ sprint 3, không tự nghĩ thuật toán | Đối chiếu kết quả với `go-feature-flag` trên cùng input |
| R4 | SSE không ổn định qua proxy | Trung bình | Trung bình | Heartbeat 25s, có fallback polling | Tắt SSE, chỉ dùng polling 10s — vẫn demo được |
| R5 | Thành viên bỏ ngang/bận | Trung bình | **Cao** | Không để ai độc quyền một module, review chéo PR | Lead gánh, cắt scope tương ứng |
| R6 | Live demo hỏng lúc bảo vệ | Trung bình | **Cao** | **Quay video demo từ tuần 14** | Bật video |
| R7 | Hội đồng chất vấn "chỉ là clone Unleash" | **Cao** | **Cao** | Chuẩn bị sẵn Phần K, có bảng so sánh tính năng | Trình bày điểm khác biệt + số liệu thực nghiệm |
| R8 | Vướng license khi dùng code tham chiếu | Thấp | Trung bình | Không copy-paste code; chỉ học thiết kế; ghi nguồn đầy đủ | Viết lại phần vi phạm |
| R9 | Hiệu năng kém khi load test | Trung bình | Trung bình | Cache Redis từ sprint 2, index đúng từ đầu | Thêm connection pool, tăng TTL cache |
| R10 | Frontend rule builder quá phức tạp, tốn thời gian | **Cao** | Trung bình | Làm bản đơn giản trước (form phẳng), nâng cấp sau | Cho nhập JSON có validate làm phương án dự phòng |

---

## PHẦN R. SẢN PHẨM BÀN GIAO

### R.1. Danh mục bàn giao

1. **Mã nguồn** — repo GitHub, có README, LICENSE, CONTRIBUTING
2. **Báo cáo** — bản Word/PDF theo mẫu của khoa
3. **Slide bảo vệ** — 20–25 trang
4. **Video demo** — 5–8 phút, có thuyết minh
5. **Tài liệu kỹ thuật** — SRS, kiến trúc, ERD, OpenAPI spec, ADR
6. **Tài liệu SDK** — hướng dẫn tích hợp, ví dụ code
7. **Bộ dữ liệu mẫu** — seed script
8. **Báo cáo kiểm thử** — độ phủ, kết quả load test, checklist bảo mật

### R.2. Bố cục báo cáo đề xuất

| Chương | Nội dung | Trang |
|---|---|---|
| Mở đầu | Lý do chọn đề tài, mục tiêu, phạm vi, phương pháp | 4–6 |
| 1. Cơ sở lý thuyết | Feature toggle (phân loại Martin Fowler), progressive delivery, trunk-based development, config center, chuẩn OpenFeature | 12–15 |
| 2. Khảo sát hiện trạng | Phân tích Unleash, Flagsmith, GO Feature Flag, Flipt, Apollo — bảng so sánh, điểm mạnh/yếu, **khoảng trống mà đồ án lấp** | 10–12 |
| 3. Phân tích yêu cầu | Actor, use case, user story, yêu cầu chức năng & phi chức năng | 12–15 |
| 4. Thiết kế hệ thống | Kiến trúc C4, ERD, thiết kế API, **thuật toán đánh giá và bucketing (mục quan trọng nhất)**, thiết kế giao diện | 20–25 |
| 5. Triển khai | Công nghệ, cấu trúc mã nguồn, các module chính, đoạn code tiêu biểu, SDK | 15–20 |
| 6. Kiểm thử & đánh giá | Chiến lược test, độ phủ, **biểu đồ phân bố bucketing**, kết quả load test, so sánh với Unleash | 12–15 |
| 7. Kết luận | Kết quả đạt được, hạn chế, hướng phát triển | 3–4 |
| Phụ lục | API reference, hướng dẫn cài đặt, ADR | — |

### R.3. Hai mươi câu hỏi hội đồng có thể hỏi — chuẩn bị trước

1. Feature flag khác gì với `if` thường trong code?
2. Tại sao không dùng file cấu hình rồi restart service?
3. Đồ án khác gì Unleash và Flagsmith? *(→ Phần K)*
4. Thuật toán chia phần trăm hoạt động thế nào? Tại sao dùng MurmurHash3?
5. Nếu tăng rollout từ 10% lên 20%, user cũ có bị đổi nhánh không? Tại sao? *(→ tính monotonic)*
6. Tại sao phải ghép `flag_key` vào chuỗi băm?
7. Nếu server FlagOps sập thì ứng dụng khách ra sao? *(→ fail-safe, cache cuối cùng)*
8. Làm sao đảm bảo cùng một user luôn thấy cùng một phiên bản?
9. Độ trễ từ lúc bật flag đến lúc ứng dụng nhận là bao lâu? Đo thế nào?
10. Tại sao tách `CLIENT` key và `SERVER` key?
11. Nếu flag key bị lộ ra client thì có nguy hiểm không?
12. Lưu snapshot toàn bộ cho mỗi release có lãng phí không? Tại sao không lưu diff?
13. Giá trị bí mật được bảo vệ thế nào? Master key để ở đâu?
14. Hệ thống chịu được bao nhiêu request/giây? Nút thắt cổ chai ở đâu?
15. Bảng `evaluation_event` sẽ rất lớn — xử lý thế nào? *(→ partition + retention)*
16. Tại sao chọn SSE mà không dùng WebSocket?
17. Làm sao phát hiện flag chết? Thuật toán tính điểm nợ kỹ thuật ra sao?
18. Có tuân thủ GDPR/bảo vệ dữ liệu cá nhân không? *(→ hash `context_key`)*
19. Nếu triển khai nhiều instance API thì cache đồng bộ thế nào? *(→ Redis Pub/Sub + ruleset_version)*
20. Hướng phát triển tiếp theo là gì?

---

## PHẦN S. CHECKLIST TUẦN 1

Đánh dấu từng mục. Không bỏ qua mục nào.

**Thứ Hai**
- [ ] Đọc lại đề bài, viết lại bằng lời của nhóm trong 1 trang
- [ ] Họp chốt scope: liệt kê MUST / SHOULD / OUT, cả nhóm đồng ý
- [ ] Chọn 2 hướng khác biệt trong Phần K
- [ ] Tạo GitHub org + repo `flagops`, mời cả nhóm
- [ ] Tạo GitHub Project board với 5 cột

**Thứ Ba**
- [ ] `docker compose up` Flagsmith, thao tác đủ: tạo flag, tạo segment, tạo rule, remote config
- [ ] Chụp màn hình toàn bộ luồng, ghi chú cái gì hay cái gì dở
- [ ] `docker compose up` Unleash, so sánh UX với Flagsmith

**Thứ Tư**
- [ ] Clone và đọc `go-feature-flag`: file `internal/flag/`, hiểu cấu trúc rule và cách tính percentage
- [ ] Đọc OpenFeature spec, phần `specification/sections/` — ghi ra danh sách reason code và error code
- [ ] Viết `docs/adr/001-tuan-thu-openfeature.md`

**Thứ Năm**
- [ ] Đọc tài liệu thiết kế Apollo: namespace, release, rollback, grayscale
- [ ] Vẽ ERD bằng dbdiagram.io hoặc Mermaid, đối chiếu với Phần F của tài liệu này
- [ ] Review ERD cả nhóm, chốt

**Thứ Sáu**
- [ ] Viết `docs/04-api-spec.yaml` — tối thiểu 25 endpoint
- [ ] Dựng khung backend FastAPI, chạy được `/health`
- [ ] Viết migration Alembic đầu tiên
- [ ] Dựng khung frontend Vite + React + Tailwind, chạy được

**Thứ Bảy**
- [ ] Viết `docker-compose.yml` hoàn chỉnh — `docker compose up` chạy được khung rỗng
- [ ] Dựng CI GitHub Actions, chạy xanh
- [ ] Cấu hình pre-commit: ruff, black, eslint, prettier
- [ ] Viết `README.md` khung

**Chủ Nhật**
- [ ] Viết báo cáo khảo sát 8–10 trang → Chương 2 báo cáo cuối kỳ
- [ ] Chuẩn bị slide báo cáo tiến độ tuần 1 cho giảng viên
- [ ] Lên backlog chi tiết cho Sprint 1, chia task, gán người

**Cổng kiểm soát cuối tuần 1 — phải đạt đủ 4 mục:**
- [ ] ERD hoàn chỉnh và được cả nhóm duyệt
- [ ] OpenAPI spec có ≥ 25 endpoint
- [ ] `docker compose up` chạy được, CI xanh
- [ ] Báo cáo khảo sát 8–10 trang hoàn thành

---

## PHỤ LỤC: LỆNH THAM KHẢO NHANH

```bash
# Khảo sát — chạy thử các hệ thống tham chiếu
curl -o flagsmith.yml https://raw.githubusercontent.com/Flagsmith/flagsmith/main/docker-compose.yml
docker compose -f flagsmith.yml up -d          # http://localhost:8000

git clone https://github.com/Unleash/unleash.git && cd unleash
docker compose up -d                            # http://localhost:4242 (admin/unleash4all)

# Dự án của nhóm
make up          # docker compose up -d --build
make migrate     # alembic upgrade head
make seed        # nạp dữ liệu mẫu
make test        # pytest + vitest
make test-engine # chỉ test engine, bắt buộc phủ >= 95%
make load        # k6 run load-tests/k6/evaluate.js
make lint        # ruff + mypy + eslint
```

---

*Tài liệu này là kế hoạch làm việc, không phải bản cuối cùng. Cập nhật lại sau mỗi sprint review và ghi lại thay đổi vào `docs/adr/`.*
