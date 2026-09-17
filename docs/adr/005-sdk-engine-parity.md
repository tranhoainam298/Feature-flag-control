# ADR-005: Chiến lược Tái sử dụng Evaluation Engine cho Python SDK và Parity Testing

## Trạng thái
Accepted

## Ngày
2026-09-17

## Ngữ cảnh (Context)
Theo quy tắc cốt lõi của FlagOps:
- Evaluation Engine phải là một hàm thuần (pure function), zero I/O, không truy cập DB/network/Redis, và hoàn toàn tất định (deterministic).
- Engine được thiết kế để dùng chung ở cả 3 nơi: máy chủ FlagOps (Backend Server), Relay Proxy, và ứng dụng khách (Python SDK in-process evaluation).
- **Cấm viết lại engine lần thứ hai bằng logic khác**, vì bất kỳ sai lệch nhỏ nào trong thuật toán băm MurmurHash3, chuẩn hóa kiểu, hay thứ tự duyệt rule đều sẽ dẫn đến kết quả đánh giá không đồng nhất giữa client và server.

Khi xây dựng package Python SDK độc lập tại `sdk/python/` (tên package: `flagops`), có 2 phương án khả thi để chia sẻ engine:
1. **Tách `app/engine/` thành package độc lập riêng (`flagops-engine`)** và đưa vào PyPI/monorepo dependencies.
2. **Vendor có kiểm soát (Controlled Copy)** `app/engine/` vào `sdk/python/flagops/engine/` và thiết lập **bộ kiểm thử đối chiếu tự động (Parity Test)** đảm bảo tính đồng nhất 100% từng byte mã nguồn giữa hai bản.

## Quyết định (Decision)

Chúng tôi quyết định chọn **Phương án 2: Vendor có kiểm soát kèm Parity Test tự động**:

### 1. Cơ cấu mã nguồn
- Thư mục `backend/app/engine/` và `sdk/python/flagops/engine/` chứa các file hoàn toàn đồng nhất:
  - `__init__.py`
  - `types.py`
  - `operators.py`
  - `bucketing.py`
  - `matcher.py`
  - `evaluator.py`
- Toàn bộ import nội bộ giữa các file trong engine được chuẩn hóa thành relative import (`from .types import ...`, `from .bucketing import bucket`), cho phép engine hoạt động nguyên vẹn khi nằm trong namespace `app.engine` của backend hoặc `flagops.engine` của SDK.

### 2. Kiểm thử đối chiếu tự động (Automated Parity Testing)
- File kiểm thử [`sdk/python/tests/test_engine_parity.py`](file:///d:/python/feature%20flag/sdk/python/tests/test_engine_parity.py) tự động quét toàn bộ cây file `.py` của engine giữa `backend/` và `sdk/`, xác nhận:
  1. Mọi file tồn tại ở cả 2 bên.
  2. Nội dung text của từng file là giống hệt nhau 100%.
  3. Bất kỳ thay đổi nào trên backend engine mà chưa đồng bộ sang SDK sẽ lập tức làm rớt CI.

### 3. Lý do lựa chọn (So sánh với Phương án 1)
- **Độc lập và tự đóng gói (Self-contained)**: Người dùng cài đặt SDK chỉ cần `pip install flagops` để nhận về một file wheel duy nhất (`.whl`), không phát sinh dependency lồng nhau (transitive private package dependencies).
- **Triết lý tối giản (`ponytail`)**: Tránh sự cồng kềnh của việc quản lý nhiều phiên bản semantic versioning, build pipeline, và phát hành nhiều package nhỏ trong một dự án monorepo.
- **Bảo toàn Purity**: Cả 2 bản đều tuân thủ nguyên tắc không I/O, chỉ phụ thuộc `mmh3` và `packaging`.

## Hệ quả
- Khi có bất kỳ cải tiến nào trong logic engine ở backend, lập tức chạy script/sao chép sang SDK và test parity sẽ bảo chứng tính toàn vẹn.
- SDK chạy đánh giá local in-process đạt kết quả hoàn toàn trùng khớp với API evaluate của backend server.
