# ADR-008: Vendor trực tiếp external skills vào repository thay vì dùng plugin/marketplace

## Trạng thái
Accepted

## Ngày
2026-09-16

## Ngữ cảnh (Context)
Để nâng cao chất lượng kỹ thuật toàn diện cho đồ án FlagOps, hệ thống cần bổ sung các tiêu chuẩn và kỹ năng chuyên sâu:
1. **Chất lượng code Python**: Giảm thiểu over-engineering, ưu tiên code tối giản (minimalism) theo tinh thần YAGNI và tận dụng thư viện chuẩn.
2. **Chất lượng thị giác UI/UX**: Tránh giao diện demo rập khuôn, thiếu cá tính ("anti-slop"), tuân thủ chuẩn thiết kế web hiện đại.
3. **Kỷ luật kỹ thuật**: Áp dụng quy trình Test-Driven Development (TDD), điều tra gỡ lỗi có hệ thống (systematic debugging), và kiểm chứng nghiệm thu nghiêm ngặt trước khi đóng task (verification before completion).

Cộng đồng mã nguồn mở đã có các skill chất lượng cao giải quyết chính xác các vấn đề trên (như `ponytail`, `taste-skill`, `vercel-labs/agent-skills`, `superpowers`). Tuy nhiên, nhóm cần một giải pháp triển khai nhất quán cho mọi thành viên và mọi công cụ trợ lý AI (Claude Code, Google Antigravity, OpenCode, Cursor) mà không làm ô nhiễm môi trường toàn cục của máy phát triển.

## Quyết định (Decision)
Chúng tôi quyết định **vendor trực tiếp** (chép mã nguồn kèm thông tin nguồn gốc, license MIT và commit hash cố định) 7 external skills tuyển chọn vào thư mục dự án:
- Thư mục chuẩn Claude Code: `.claude/skills/<ten-skill>/`
- Thư mục mirror Antigravity: `.agents/skills/<ten-skill>/`

Danh sách 7 skill được vendor:
1. `ponytail` (nguồn: DietrichGebert/ponytail) — Code tối giản, chống over-engineering.
2. `taste-skill` (nguồn: Leonxlnx/taste-skill, `design-taste-frontend`) — Thẩm mỹ thị giác UI anti-slop cho dashboard.
3. `web-design-guidelines` (nguồn: vercel-labs/agent-skills) — Tiêu chuẩn thiết kế giao diện web UX/UI.
4. `writing-guidelines` (nguồn: vercel-labs/agent-skills) — Quy chuẩn viết tài liệu và microcopy rõ ràng.
5. `tdd` (nguồn: obra/superpowers, `test-driven-development`) — Kỷ luật Red-Green-Refactor cho engine/pure logic.
6. `systematic-debugging` (nguồn: obra/superpowers) — Điều tra lỗi có hệ thống theo phương pháp khoa học.
7. `verification-before-completion` (nguồn: obra/superpowers) — Kiểm tra và thu thập bằng chứng nghiệm thu trước khi hoàn thành task.

Mỗi skill bắt buộc phải đi kèm file `SOURCE.md` ghi nhận URL gốc, giấy phép MIT, commit hash đã chốt, ngày vendor và lý do sử dụng. Đồng thời, cấu hình con trỏ luôn-bật được tích hợp vào `AGENTS.md`.

## Phương án thay thế (Alternatives Considered)

| Phương án | Ưu điểm | Nhược điểm | Lý do không chọn |
|-----------|---------|------------|-------------------|
| Cài qua `/plugin marketplace` hoặc IDE extension toàn cục | Cài nhanh trên máy cá nhân hiện tại | Bị khóa vào một IDE duy nhất, ghi đè thư mục global (`~/.claude`, `~/.gemini`), người khác clone repo về sẽ không có skill | Vi phạm tính độc lập, không di động (portable) và khó tái lập khi chấm đồ án |
| Dùng Git Submodules | Trỏ trực tiếp đến repo upstream, dễ pull cập nhật | Phức tạp khi clone repo (`--recurse-submodules`), dễ gây lỗi trạng thái detached HEAD hoặc lỗi CI build | Tăng gánh nặng thao tác Git cho nhóm và giảng viên khi review |
| Tự viết 100% toàn bộ skill | Toàn quyền kiểm soát mọi câu chữ | Mất nhiều thời gian, thiếu các benchmark đo lường thực tế đã được cộng đồng kiểm chứng (như benchmark giảm ~54% dòng code của ponytail) | Không tối ưu thời gian phát triển đồ án (reinventing the wheel) |

## Hệ quả (Consequences)

### Tích cực
- **Tính di động 100% (Portability)**: Mọi thành viên chỉ cần clone repository về là có đầy đủ bộ skill và rule, hoạt động tức thì trên Claude Code, Antigravity, OpenCode hay Cursor.
- **An toàn môi trường**: Không can thiệp hay ghi bất kỳ tệp tin nào vào thư mục global của hệ điều hành.
- **Tính minh bạch và tái lập**: Mỗi skill có `SOURCE.md` với commit hash cố định, phục vụ trích dẫn học thuật rõ ràng trong báo cáo đồ án.
- **Tập trung hóa chỉ dẫn**: `AGENTS.md` đóng vai trò bảng điều hướng súc tích, tránh phình to ngữ cảnh không cần thiết.

### Tiêu cực (Trade-off)
- Khi upstream của các skill bên ngoài có bản vá lỗi hoặc tính năng mới, nhóm phải chủ động cập nhật thủ công (manual sync).
- Repository tăng thêm dung lượng tài liệu (~100 KB text files).
