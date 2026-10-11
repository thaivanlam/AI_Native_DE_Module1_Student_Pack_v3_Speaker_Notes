# Báo cáo kiểm thử Idempotency (Bài 5)

**Kết luận: ĐẠT.** Chạy lại pipeline với cùng dữ liệu API không làm tăng số dòng và không sinh bản ghi trùng trong PostgreSQL: lần chạy lại có `inserted = 0`, toàn bộ bản ghi chuyển thành `updated`, `COUNT(*)` giữ nguyên và luôn bằng `COUNT(DISTINCT khóa chính)`.

- Ngày kiểm thử: 2026-10-11
- Database: PostgreSQL 16 (`ecommerce`, schema `core`), container `ecommerce-postgres`
- Nguồn: Mock API `http://localhost:8000`, 5 resource (trọng tâm: 600 orders)
- Log gốc: [evidence/06-upsert-log.txt](evidence/06-upsert-log.txt) (Run 1), [evidence/06-idempotency-log.txt](evidence/06-idempotency-log.txt) (Run 2, Run 3)

## 1. Kịch bản kiểm thử

Nạp cùng một tập dữ liệu API vào `core` nhiều lần liên tiếp và so sánh trạng thái database sau mỗi lần.

| Lần chạy | Thời điểm | Nội dung | RAW |
|---|---|---|---|
| Run 1 (Cold Start) | 11:10:27 | Nạp lần đầu dữ liệu API vào `core` | `data/raw/20261011T040548Z/` |
| Run 2 (Re-run) | 11:14:37 | Chạy lại toàn bộ pipeline: gọi API, lưu RAW mới, upsert | `data/raw/20261011T041437Z/` |
| Run 3 (Re-run) | 11:14:39 | Nạp lại chính RAW của Run 2 thêm một lần | `data/raw/20261011T041437Z/` |

Dữ liệu của Run 2 đã được so sánh với Run 1 và giống hệt nhau trên cả 5 file RAW, nên đây đúng là "cùng một tập dữ liệu".

**Về "Cold Start":** bảng `core.orders` không rỗng trước Run 1 mà đã có sẵn 5000 đơn hàng từ các buổi trước. "Cold" ở đây nghĩa là 600 đơn hàng của API (`ORD005001` đến `ORD005600`) chưa từng có trong database. Vì vậy `COUNT(*)` là 5600 chứ không phải 600 như mẫu đề bài.

Run 1 chính là lần nạp của Bài 4. Database không được xóa để nạp lại từ đầu; số liệu Run 1 lấy từ log của lần nạp đó.

## 2. Câu lệnh thực hiện

```bash
# Run 1: lấy dữ liệu API về RAW, rồi nạp RAW vào core
python scripts/demo_fetch.py                        # tạo data/raw/20261011T040548Z/
python scripts/demo_upsert.py 20261011T040548Z      # upsert vào core

# Run 2 + Run 3: chạy lại pipeline và đối soát
python scripts/demo_idempotency.py 20261011T040548Z > docs/evidence/06-idempotency-log.txt 2>&1
```

Run 2 tương đương với việc chạy lại pipeline bằng dòng lệnh:

```bash
python -m src.pipeline --load
```

## 3. Số liệu nghiệm thu trên `core.orders`

| Chỉ số | Trước Run 1 | Run 1 (Cold Start) | Run 2 (Re-run) | Run 3 (Re-run) |
|---|---|---|---|---|
| Số bản ghi đầu vào | — | 600 | 600 | 600 |
| `inserted` | — | **600** | **0** | **0** |
| `updated` | — | **0** | **600** | **600** |
| `SELECT COUNT(*)` | 5000 | **5600** | **5600** | **5600** |
| `SELECT COUNT(DISTINCT order_id)` | — | 5600 ¹ | **5600** | **5600** |
| md5 nội dung toàn bảng | — | `3d6df900bbdf...` ¹ | `3d6df900bbdf...` | `3d6df900bbdf...` |

¹ Đo ngay trước Run 2, tức là trạng thái do Run 1 để lại. Tại thời điểm Run 1, log chỉ ghi nhận 600/600 khóa của RAW có mặt trong database và không trùng.

Đối chiếu với yêu cầu:

| Yêu cầu | Kết quả | Đánh giá |
|---|---|---|
| Lần 2: `inserted` phải bằng 0 | 0 | Đạt |
| Lần 2: `updated` bằng tổng số bản ghi | 600 / 600 | Đạt |
| `COUNT(*)` không đổi giữa các lần chạy | 5600 → 5600 → 5600 | Đạt |
| `COUNT(*)` = `COUNT(DISTINCT order_id)` | 5600 = 5600 | Đạt |

## 4. Số liệu cả 5 bảng

Pipeline nạp cả 5 resource, nên tính bất biến được kiểm tra trên toàn bộ.

| Bảng | Đầu vào | Run 1 inserted / updated | Run 2 inserted / updated | Run 3 inserted / updated | `COUNT(*)` sau Run 1 | sau Run 2 | sau Run 3 |
|---|---|---|---|---|---|---|---|
| `core.customers` | 100 | 50 / 50 | 0 / 100 | 0 / 100 | 1050 | 1050 | 1050 |
| `core.products` | 50 | 20 / 30 | 0 / 50 | 0 / 50 | 520 | 520 | 520 |
| `core.orders` | 600 | 600 / 0 | 0 / 600 | 0 / 600 | 5600 | 5600 | 5600 |
| `core.order_items` | 1533 | 1533 / 0 | 0 / 1533 | 0 / 1533 | 14250 | 14250 | 14250 |
| `core.payments` | 536 | 536 / 0 | 0 / 536 | 0 / 536 | 5053 | 5053 | 5053 |

Ở Run 1, `customers` và `products` có cả `updated` vì một phần khách hàng và sản phẩm của API đã tồn tại sẵn trong `core`.

Sau Run 2 và Run 3, ở cả 5 bảng `COUNT(*)` bằng `COUNT(DISTINCT khóa chính)` và md5 nội dung toàn bảng không đổi.

## 5. SQL đối soát tính toàn vẹn

```sql
SELECT COUNT(*) FROM core.orders;
SELECT COUNT(DISTINCT order_id) FROM core.orders;
```

| Câu lệnh | Sau Run 1 | Sau Run 2 | Sau Run 3 |
|---|---|---|---|
| `SELECT COUNT(*) FROM core.orders` | 5600 | 5600 | 5600 |
| `SELECT COUNT(DISTINCT order_id) FROM core.orders` | 5600 | 5600 | 5600 |

Kiểm tra bổ sung, tìm khóa xuất hiện nhiều hơn một lần (kết quả: 0 dòng):

```sql
SELECT order_id, COUNT(*)
FROM core.orders
GROUP BY order_id
HAVING COUNT(*) > 1;
```

Kiểm tra nội dung không đổi, không chỉ số dòng. Câu lệnh dưới băm toàn bộ nội dung bảng theo thứ tự khóa chính; kết quả giống nhau trước và sau mỗi lần chạy lại:

```sql
SELECT md5(string_agg(t::text, '|' ORDER BY order_id)) FROM core.orders t;
```

## 6. Vì sao pipeline idempotent

- **Khóa chính + `ON CONFLICT`:** mỗi bảng `core` có khóa chính, và câu lệnh nạp là `INSERT ... ON CONFLICT (khóa chính) DO UPDATE SET cột = EXCLUDED.cột`. Bản ghi có khóa đã tồn tại được cập nhật tại chỗ thay vì chèn thêm.
- **Cập nhật bằng chính giá trị đầu vào:** các cột được gán thẳng từ dữ liệu nguồn, không cộng dồn hay sinh giá trị mới, nên nạp cùng dữ liệu nhiều lần cho cùng một kết quả.
- **Cột `ingested_at` không bị ghi đè:** cột này không nằm trong dữ liệu gửi lên nên giữ nguyên thời điểm chèn đầu tiên. Đây là lý do md5 toàn bảng không đổi qua các lần chạy.
- **Transaction theo bảng:** mỗi bảng nạp trong một transaction (`engine.begin()`); nếu lỗi giữa chừng thì cả lô rollback, không để lại trạng thái nạp dở.

## 7. Giới hạn của kiểm thử

- Mock API trả dữ liệu tĩnh, nên chưa kiểm thử trường hợp dữ liệu nguồn thay đổi giữa hai lần chạy (khi đó `updated` sẽ ghi đè giá trị mới, số dòng vẫn không tăng).
- Bản ghi bị xóa ở nguồn không bị xóa khỏi `core`; upsert chỉ thêm và cập nhật.
- RAW không idempotent theo thiết kế: mỗi lần chạy tạo một thư mục `data/raw/<run_id>/` mới để giữ nguyên bản gốc của từng lần.
