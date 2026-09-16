# S02: Auth & RBAC — Authentication, Token Management & Role-Based Access Control

## Ngày hoàn thành
2026-09-16

## Implemented
- **Mã hóa mật khẩu Argon2id & JWT (`backend/app/core/security.py`)**:
  - Mã hóa mật khẩu sử dụng `passlib[argon2]` (Argon2id), không dùng bcrypt hay SHA-256 trần.
  - JWT access token TTL 30 phút, refresh token TTL 7 ngày.
  - Refresh token sinh chuỗi ngẫu nhiên `secrets.token_urlsafe(32)` kèm `jti`, chỉ lưu SHA-256 hash trong database (`refresh_token_hash` trong bảng `user`), hỗ trợ thu hồi token từ phía server.
  - Cảnh báo bảo mật khi chạy production nếu `SECRET_KEY` chưa được thay đổi khỏi giá trị mặc định.
  - Hàm login dùng timing-safe dummy hash khi người dùng không tồn tại để chống tấn công user enumeration qua chênh lệch thời gian xử lý.
- **FastAPI Dependencies & RBAC (`backend/app/core/deps.py`, `backend/app/core/permissions.py`)**:
  - `get_current_user`: Trích xuất Bearer token, giải mã JWT, kiểm tra `is_active`. Trả về 401 với thông báo lỗi thống nhất.
  - `require_role(*roles)`: Kiểm tra vai trò tối thiểu của user theo phân cấp `OWNER > ADMIN > DEVELOPER > VIEWER`.
  - `require_project_access(...)`: Kiểm tra quyền truy cập dự án theo tổ chức, trả về **404 Not Found** (không trả 403) khi truy cập chéo tổ chức để tránh làm lộ sự tồn tại của tài nguyên.
- **Pydantic Schemas (`backend/app/schemas/auth.py`)**:
  - `RegisterRequest`: Kiểm tra email định dạng chuẩn `EmailStr`, mật khẩu tối thiểu 8 ký tự, có chữ hoa và chữ số.
  - `LoginRequest`, `TokenResponse`, `RefreshTokenRequest`, `UserResponse`.
  - **Tuyệt đối không để lộ trường `password` hay `password_hash` trong bất kỳ response nào**.
- **Auth Service & API Routers (`backend/app/services/auth.py`, `backend/app/api/v1/auth.py`)**:
  - `POST /api/v1/auth/register`: Đăng ký tài khoản mới (status 201). Trả 409 nếu trùng email.
  - `POST /api/v1/auth/login`: Đăng nhập, trả cặp access_token và refresh_token. Trả 401 với thông điệp đồng nhất cho cả sai mật khẩu và user không tồn tại.
  - `POST /api/v1/auth/refresh`: Làm mới token với cơ chế refresh token rotation.
  - `POST /api/v1/auth/logout`: Đăng xuất và xóa `refresh_token_hash`.
  - `GET /api/v1/auth/me`: Lấy thông tin user hiện tại (yêu cầu Bearer token).
- **Alembic Migration (`backend/alembic/versions/002_user_refresh_token.py`)**:
  - Bổ sung cột `refresh_token_hash VARCHAR(64)` vào bảng `user`.

## Tests
- **Số test đã viết**: 15 test cases tại `backend/app/tests/test_auth.py`:
  1. `test_register_success`: Đăng ký thành công (201), không lộ password/hash.
  2. `test_register_duplicate_email_409`: Báo lỗi 409 CONFLICT khi trùng email.
  3. `test_register_invalid_email_422`: Báo lỗi 422 VALIDATION_ERROR khi email sai định dạng.
  4. `test_register_weak_password_422`: Báo lỗi 422 VALIDATION_ERROR khi mật khẩu quá yếu.
  5. `test_login_success`: Đăng nhập thành công trả đủ access_token và refresh_token.
  6. `test_login_wrong_password_401`: Báo lỗi 401 khi sai mật khẩu.
  7. `test_login_nonexistent_user_401_same_message`: Báo lỗi 401 với thông điệp giống hệt sai mật khẩu (chống user enumeration).
  8. `test_expired_token_401`: Token hết hạn trả 401.
  9. `test_wrong_signature_token_401`: Token giả mạo chữ ký trả 401.
  10. `test_no_token_401`: Không truyền Bearer token trả 401.
  11. `test_refresh_success`: Làm mới access token thành công.
  12. `test_refresh_revoked_token_401`: Refresh token đã bị thu hồi trả 401.
  13. `test_me_success`: Endpoint GET /me trả đúng thông tin người dùng.
  14. `test_viewer_cannot_write_403`: Role VIEWER bị chặn 403 FORBIDDEN khi ghi.
  15. `test_password_never_in_any_response`: Đảm bảo không lộ thông tin nhạy cảm.
- **Kết quả kiểm thử**: **15 passed (100%)**.

## Known Issues
- Không có lỗi tồn đọng.

## Dependencies
- Slice này phụ thuộc: S00 (Docker, FastAPI framework), S01 (User & Membership models).
- Slice phụ thuộc slice này: S03 (Tenancy & CRUD Organization / Project / Environment / API Key).
