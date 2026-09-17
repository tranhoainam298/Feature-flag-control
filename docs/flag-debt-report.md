# FlagOps Flag Scanner Report

## Tổng quan

- **Tổng số flag trong code:** 20
- **DEAD (Cờ đã archived nhưng còn trong code):** 0
- **STALE (Cờ có điểm nợ cao, cần dọn dẹp):** 0
- **UNDECLARED (Cờ chưa khai báo trên server):** 0
- **ORPHAN (Cờ trên server nhưng không có trong code):** 0
- **OK (Cờ hoạt động bình thường):** 0

## Chi tiết cờ tính năng

| Flag Key | Trạng thái | Điểm nợ | Số lần xuất hiện | Khuyến nghị hành động |
|---|---|---|---|---|
| `checkout-v2` | **UNKNOWN** | — | 13 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `key` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `disabled-flag` | **UNKNOWN** | — | 2 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `non-existent-flag` | **UNKNOWN** | — | 2 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `banner-color` | **UNKNOWN** | — | 3 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `max-items` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `feature-config` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `any-flag` | **UNKNOWN** | — | 6 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `remote-flag` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `f-float` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `f-bool` | **UNKNOWN** | — | 2 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `f-invalid` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `non-existent-key` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `banner-text` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `max-connections` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `ui-theme-config` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `new-homepage` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `payment-v2` | **UNKNOWN** | — | 2 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `dead-feature-flag` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |
| `dark-mode` | **UNKNOWN** | — | 1 | Chạy ở chế độ offline, chưa đối chiếu với máy chủ |

## Danh sách vị trí trong mã nguồn

### `checkout-v2` (UNKNOWN)
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
- `D:\python\feature flag\sdk\python\tests\test_client.py:28`
  ```
  assert client.is_enabled("checkout-v2", {"userId": "regular-user"}) is False
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:31`
  ```
  assert client.is_enabled("checkout-v2", {"targetingKey": "u2", "is_beta": True}) is True
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:34`
  ```
  assert client.is_enabled("checkout-v2", {"targetingKey": "user-vip"}) is True
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:98`
  ```
  res = client.is_enabled("checkout-v2", {"is_beta": True})
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:127`
  ```
  assert client.is_enabled("checkout-v2", {"is_beta": True}) is True
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:134`
  ```
  assert client.is_enabled("checkout-v2", {"is_beta": True}) is True
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:256`
  ```
  assert client.is_enabled("checkout-v2", {"is_beta": True}) is True
  ```
- `D:\python\feature flag\sdk\python\tests\test_openfeature.py:451`
  ```
  sdk_bool = client.get_boolean("checkout-v2", context=ctx_dict, default=False)
  ```
- `D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\app.py:11`
  ```
  if self.client.is_enabled("checkout-v2"):
  ```
- `D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\service.ts:9`
  ```
  const isV2 = await this.client.isEnabled("checkout-v2");
  ```

### `key` (UNKNOWN)
- `D:\python\feature flag\frontend\src\features\flags\CreateFlagModal.tsx:104`
  ```
  helperText="Unique identifier used in code via client.is_enabled('key')"
  ```

### `disabled-flag` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_client.py:37`
  ```
  assert client.is_enabled("disabled-flag") is False
  ```
- `D:\python\feature flag\sdk\python\tests\test_openfeature.py:471`
  ```
  sdk_dis = client.get_boolean("disabled-flag", context=ctx_dict, default=True)
  ```

### `non-existent-flag` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_client.py:40`
  ```
  assert client.is_enabled("non-existent-flag", default=True) is True
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:41`
  ```
  assert client.is_enabled("non-existent-flag", default=False) is False
  ```

### `banner-color` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_client.py:55`
  ```
  assert client.get_string("banner-color", default="green") == "blue"
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:64`
  ```
  assert client.get_variant("banner-color", default="none") == "blue"
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:67`
  ```
  eval_res = client.get_evaluation("banner-color")
  ```

### `max-items` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_client.py:58`
  ```
  assert client.get_number("max-items", default=10) == 50
  ```

### `feature-config` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_client.py:61`
  ```
  assert client.get_json("feature-config", default={}) == {"theme": "dark", "retries": 3}
  ```

### `any-flag` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_client.py:157`
  ```
  assert client.is_enabled("any-flag", default=False) is False
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:158`
  ```
  assert client.is_enabled("any-flag", default=True) is True
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:159`
  ```
  assert client.get_string("any-flag", default="fallback") == "fallback"
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:160`
  ```
  assert client.get_number("any-flag", default=99) == 99
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:161`
  ```
  assert client.get_json("any-flag", default={"a": 1}) == {"a": 1}
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:163`
  ```
  eval_res = client.get_evaluation("any-flag", default="def")
  ```

### `remote-flag` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_client.py:219`
  ```
  val = client.get_string("remote-flag", default="def")
  ```

### `f-float` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_client.py:290`
  ```
  assert client.get_number("f-float", default=0) == 3.14
  ```

### `f-bool` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_client.py:291`
  ```
  assert client.get_number("f-bool", default=42) == 42
  ```
- `D:\python\feature flag\sdk\python\tests\test_client.py:293`
  ```
  assert client.get_boolean("f-bool", default=False) is True
  ```

### `f-invalid` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_client.py:292`
  ```
  assert client.get_number("f-invalid", default=99) == 99
  ```

### `non-existent-key` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_integration.py:91`
  ```
  missing_on = client.is_enabled("non-existent-key", default=False)
  ```

### `banner-text` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_openfeature.py:456`
  ```
  sdk_str = client.get_string("banner-text", context=ctx_dict, default="def")
  ```

### `max-connections` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_openfeature.py:461`
  ```
  sdk_int = client.get_number("max-connections", context=ctx_dict, default=0)
  ```

### `ui-theme-config` (UNKNOWN)
- `D:\python\feature flag\sdk\python\tests\test_openfeature.py:466`
  ```
  sdk_obj = client.get_json("ui-theme-config", context=ctx_dict, default={})
  ```

### `new-homepage` (UNKNOWN)
- `D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\app.py:15`
  ```
  if self.client.get_boolean("new-homepage", default=False):
  ```

### `payment-v2` (UNKNOWN)
- `D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\app.py:24`
  ```
  val = self.client.get_string("payment-v2", default="standard")
  ```
- `D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\service.ts:16`
  ```
  const paymentVariant = this.client.getStringValue("payment-v2", "stripe");
  ```

### `dead-feature-flag` (UNKNOWN)
- `D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\app.py:27`
  ```
  if self.client.is_enabled("dead-feature-flag"):
  ```

### `dark-mode` (UNKNOWN)
- `D:\python\feature flag\tools\flag-scanner\tests\fixtures\sample-project\service.ts:14`
  ```
  const isDark = await this.openfeatureClient.getBooleanValue("dark-mode", false);
  ```
