# Project Guardrails — Quy tắc bảo vệ dự án FlagOps

## Những điều KHÔNG BAO GIỜ được làm

1. **KHÔNG sửa file `.env`** — chỉ sửa `.env.example`. File `.env` là của từng dev.
2. **KHÔNG commit secret** — API key, password, master key, JWT secret.
   Dùng `.env` + `.env.example` với placeholder.
3. **KHÔNG xóa code cũ khi chưa đọc hiểu** — đọc code trước, hiểu ngữ cảnh,
   rồi mới quyết định xóa. Dùng `git blame` nếu cần.
4. **KHÔNG tạo pseudocode thay implementation** — viết code thật, có test thật.
   File chỉ có comment mô tả là KHÔNG chấp nhận.
5. **KHÔNG viết `# TODO implement`** ở chức năng MUST — nếu là MUST thì
   phải implement ngay, không defer.
6. **KHÔNG sửa migration đã commit** — tạo migration mới thay thế.
7. **KHÔNG merge PR khi CI đỏ** — fix trước, merge sau.
8. **KHÔNG copy code từ Flagsmith/Unleash/GO Feature Flag** — chỉ học
   thiết kế, tự viết implementation. Ghi nguồn tham chiếu trong ADR.
9. **MUST xong hết mới làm SHOULD** — không nhảy sang tính năng SHOULD
   khi còn MUST chưa xong.
10. **KHÔNG phá slice trước** — test của slice trước phải vẫn xanh
    sau khi thêm slice mới.
