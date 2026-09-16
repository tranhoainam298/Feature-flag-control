# ADR-007: Thuật toán MurmurHash3 Sticky Bucketing cho Rollout tỷ lệ phần trăm

## Trạng thái
Accepted

## Ngày
2026-09-16

## Ngữ cảnh (Context)
Trong một hệ thống quản lý Feature Flag phân tán (như FlagOps), việc rollout tính năng dần dần theo tỷ lệ phần trăm (percentage rollout / canary / A-B testing) yêu cầu giải thuật phân nhóm (bucketing) phải đáp ứng đồng thời 5 đặc tính toán học khắt khe:
1. **Determinism (Tính xác định)**: Cùng một định danh người dùng (`context_value`), cờ tính năng (`flag_key`), và luật mục tiêu (`rule_id`) phải luôn luôn trả về cùng một biến thể (variation) ở mọi lần gọi, không phụ thuộc vào tiến trình hay thời điểm.
2. **Uniform Distribution (Phân bố đều)**: Giá trị băm phải phân bổ đều trên toàn bộ không gian số từ 0 đến 9999 (độ phân giải 0.01%), đảm bảo sai số phân bố trên tập mẫu lớn (< 1% với tập 10,000 users).
3. **Monotonic Rollout Continuity (Tính đơn điệu khi tăng tỷ lệ)**: Khi tăng rollout từ 10% lên 20%, **toàn bộ người dùng đã thuộc nhóm 10% cũ bắt buộc phải tiếp tục nằm trong nhóm 20% mới**. Hiện tượng người dùng nhận tính năng ở 10% nhưng bị mất khi tăng lên 20% là lỗi nghiêm trọng làm gián đoạn trải nghiệm.
4. **Inter-Flag Independence (Độc lập giữa các Flag)**: Nếu hai flag khác nhau cùng thiết lập rollout 10%, tập người dùng nhận cả hai flag phải xấp xỉ xác suất kết hợp lý thuyết ($10\% \times 10\% = 1\%$). Nếu không, một nhóm người dùng cố định sẽ luôn luôn trở thành "chuột bạch" cho mọi tính năng mới.
5. **Portability & Performance (Độc lập nền tảng & Hiệu năng cao)**: Thuật toán phải chạy thuần túy trên CPU (pure function, zero-I/O), thực thi cực nhanh (< 1 microsecond/lần), và cho kết quả giống nhau giữa Server, SDK in-process và Relay Proxy.

## Quyết định (Decision)
Chúng tôi quyết định sử dụng thuật toán **32-bit MurmurHash3** (unsigned) kết hợp kỹ thuật **Salted Hash Input** và thang chuẩn hóa 10,000 điểm:

```python
hash_input = f"{flag_key}:{rule_id}:{context_value}"
h = mmh3.hash(hash_input, seed, signed=False)
bucket_value = h % 10000

cumulative = 0.0
for var, weight in distribution:
    cumulative += weight * 100.0
    if bucket_value < cumulative:
        return var
return distribution[-1].var
```

### Các chi tiết kỹ thuật then chốt:
1. **Chuỗi băm có Salt**: Ghép `f"{flag_key}:{rule_id}:{context_value}"` thay vì chỉ băm `context_value`. Sự khác biệt của `flag_key` đóng vai trò như một salt ngẫu nhiên hóa phân vị của từng user qua các cờ khác nhau.
2. **Thang phân giải 10,000**: Phép chia `% 10000` tạo ra không gian bucket nguyên trong khoảng $[0, 9999]$, cho phép cấu hình phân vị mịn tới 0.01%, đáp ứng tốt các kịch bản canary quy mô lớn.
3. **Tích lũy đơn điệu**: Bằng cách duyệt tích lũy `weight * 100.0`, nếu biến thể `on` chiếm 10% trọng số đầu, điều kiện chọn là `bucket_value < 1000`. Khi tăng lên 20%, điều kiện mở rộng thành `bucket_value < 2000`. Do $bucket\_value < 1000 \implies bucket\_value < 2000$, tính đơn điệu được bảo toàn tuyệt đối 100%.

## Phương án thay thế (Alternatives Considered)

| Phương án | Ưu điểm | Nhược điểm | Lý do không chọn |
|---|---|---|---|
| **Python `hash()` builtin** | Có sẵn trong stdlib, không cần cài thư viện | Python áp dụng hash randomization (SipHash với salt ngẫu nhiên sinh mới ở mỗi process) | Vi phạm hoàn toàn tính ổn định giữa các process và các ngôn ngữ khác |
| **MD5 / SHA-256** | Chuẩn mật mã phổ biến, tính ngẫu nhiên cao | Chậm hơn 5–10 lần so với MurmurHash3; tốn tài nguyên CPU không cần thiết cho bài toán phi mật mã | Over-engineering cho bài toán chia bucket |
| **`random()` / `uuid4()`** | Đơn giản khi viết code | Hoàn toàn ngẫu nhiên, không có tính "dính" (sticky) | Mỗi lần tải lại trang hoặc gọi API, người dùng sẽ bị nhảy giữa các biến thể |
| **Chỉ băm `context_value`** | Input ngắn gọn | Các flag rollout 10% sẽ chọn đúng cùng 10% người dùng có hash thấp | Khiến một nhóm user luôn phải chịu rủi ro ở mọi cờ thử nghiệm |

## Kết quả kiểm chứng (Verification)
1. **Property Tests (Hypothesis)**: Đã kiểm chứng tính xác định (determinism) qua hàng nghìn chuỗi ngẫu nhiên.
2. **Kiểm chứng phân bố đều**: Mẫu 10,000 UUIDs cho tỷ lệ 50/50 đạt 49.8% : 50.2% (sai số < 0.2%).
3. **Kiểm chứng tính đơn điệu**: 20,000 users, tập 10% là tập con tuyệt đối 100% của tập 20% (`nhom_10.issubset(nhom_20)`).
4. **Kiểm chứng độc lập**: Hai flag 10% độc lập có tỷ lệ giao thoa thực tế 1.04% (lý thuyết: 1.00%), chứng minh tính hiệu quả của salt `flag_key`.
5. **Biểu đồ trực quan**: Đã xuất thành công tại [`docs/diagrams/bucketing-distribution.png`](file:///d:/python/feature%20flag/docs/diagrams/bucketing-distribution.png).
