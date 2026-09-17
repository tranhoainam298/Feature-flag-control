# FlagOps Flag Scanner Report

## Tổng quan

- **Tổng số flag trong code:** 1
- **DEAD (Cờ đã archived nhưng còn trong code):** 0
- **STALE (Cờ có điểm nợ cao, cần dọn dẹp):** 0
- **UNDECLARED (Cờ chưa khai báo trên server):** 0
- **ORPHAN (Cờ trên server nhưng không có trong code):** 4
- **OK (Cờ hoạt động bình thường):** 1

## Chi tiết cờ tính năng

| Flag Key | Trạng thái | Điểm nợ | Số lần xuất hiện | Khuyến nghị hành động |
|---|---|---|---|---|
| `dark-mode` | **ORPHAN** | — | 0 | Flag có trên server nhưng không tìm thấy trong code, có thể cân nhắc archive |
| `new-homepage` | **ORPHAN** | — | 0 | Flag có trên server nhưng không tìm thấy trong code, có thể cân nhắc archive |
| `payment-v2` | **ORPHAN** | — | 0 | Flag có trên server nhưng không tìm thấy trong code, có thể cân nhắc archive |
| `recommendation-engine` | **ORPHAN** | — | 0 | Flag có trên server nhưng không tìm thấy trong code, có thể cân nhắc archive |
| `checkout-v2` | **OK** | — | 3 | Cờ tính năng đang hoạt động bình thường |

## Danh sách vị trí trong mã nguồn

### `checkout-v2` (OK)
- `D:\python\feature flag\demo-app\main.py:93`
  ```
  checkout_eval_vn = sdk_client.get_evaluation("checkout-v2", context=vn_context, default=False)
  ```
- `D:\python\feature flag\demo-app\main.py:97`
  ```
  checkout_eval_us = sdk_client.get_evaluation("checkout-v2", context=us_context, default=False)
  ```
- `D:\python\feature flag\demo-app\main.py:198`
  ```
  eval_vn = sdk_client.get_evaluation("checkout-v2", context=vn_context, default=False)
  ```
