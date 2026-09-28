# 4. Dữ liệu

← [3. Cấu trúc thư mục](03_cau_truc_thu_muc.md) · Tiếp: [5. Database OLTP](05_database_oltp.md) →

## 4.1 Bảy thực thể

| Thực thể | Mô tả | Khoá | Ví dụ ID |
|---|---|---|---|
| `categories` | Danh mục sản phẩm, đa cấp (có danh mục cha) | `category_id` | `CAT001` |
| `customers` | Khách hàng, có segment Standard/Silver/Gold/Platinum | `customer_id` | `CUS000001` |
| `products` | Sản phẩm, thuộc 1 category, có giá bán và giá vốn | `product_id` | `PRD000001` |
| `order_status` | Bảng tra cứu 5 trạng thái đơn | `order_status` | `completed` |
| `orders` | Đơn hàng của 1 khách | `order_id` | `ORD000001` |
| `order_items` | Dòng hàng trong đơn (cầu nối orders ↔ products) | `order_item_id` | `ITM00000001` |
| `payments` | Giao dịch thanh toán của đơn | `payment_id` | `PAY000001` |

Định nghĩa từng cột: [docs/data_dictionary.csv](../docs/data_dictionary.csv).

## 4.2 Ba bộ dữ liệu

| Dataset | Seed (`data/seed/`) | Incremental 2026-07-01 | Dirty 2026-07-02 |
|---|---:|---:|---:|
| categories | 20 | — | — |
| order_status | 5 | — | — |
| customers | 1.000 | 100 | 40 |
| products | 500 | 50 | 30 |
| orders | 5.000 | 600 | 100 |
| order_items | 12.717 | 1.533 | 220 |
| payments | 4.517 | 536 | (JSON) |

| Bộ | Định dạng | Dùng ở | Mục đích |
|---|---|---|---|
| **Seed** | 7 file CSV | Buổi 2–4 | Baseline cho CORE; đơn hàng từ 2026-01-01 đến 2026-06-29 |
| **Incremental** | 4 CSV + `payments_daily.json` | Buổi 5, 6, 8 | Batch hằng ngày **sạch**: khách/sản phẩm cập nhật + đơn mới ngày 2026-07-01 |
| **Dirty** | 4 CSV + `payments_daily.json` | Buổi 7 | Batch **bẩn** có lỗi cố ý để luyện Data Quality |

Ngoài ra `mock_api/data/*.json` chứa dữ liệu phục vụ REST API (Buổi 6–8).

### Điểm cần lưu ý

- File `orders*.csv` dùng header `status`, nhưng bảng `core.orders` đặt tên cột là `order_status`. Script bootstrap map theo **vị trí cột** trong `\copy`, nên tự đổi tên khi nạp.
- Incremental chứa cả bản ghi **cập nhật** (ví dụ `CUS000001` đổi city, segment; `PRD000001` tăng giá) → pipeline phải **upsert**, không chỉ insert.
- Cột `source_system` phân biệt nguồn: `seed`, `daily_file`, `ecommerce_api`.

## 4.3 Data contract ([docs/data_contract.md](../docs/data_contract.md))

| Hạng mục | Quy ước |
|---|---|
| ID | Tiền tố + số đệm 0: `CUS000001`, `CAT001`, `PRD000001`, `ORD000001`, `ITM00000001`, `PAY000001` |
| Thời gian | ISO 8601, múi giờ `+07:00`; PostgreSQL lưu `TIMESTAMPTZ` |
| Tiền | VND, kiểu `NUMERIC(14,2)` |
| Audit | `source_system`, `ingested_at`, `created_at`, `updated_at` |

**Enum hợp lệ:**

| Trường | Giá trị |
|---|---|
| customer status | `active`, `inactive` |
| product status | `active`, `inactive`, `discontinued` |
| order status | `pending`, `confirmed`, `shipped`, `completed`, `cancelled` |
| payment status | `pending`, `success`, `failed`, `refunded` |
| payment method | `cash`, `bank_transfer`, `card`, `e_wallet` |
| channel | `web`, `mobile_app`, `social` |

## 4.4 Business rules (dùng cho validate)

1. `customer_id` duy nhất; email hợp lệ và không trùng.
2. Mỗi sản phẩm thuộc 1 category; `unit_price`, `cost_price` ≥ 0.
3. Order thuộc đúng 1 customer, có ≥ 1 order item.
4. `quantity` > 0; `discount_amount` ≥ 0 và ≤ gross (`quantity × unit_price`).
5. Status/method/channel chỉ nhận giá trị trong enum.
6. Payment phải trỏ tới order tồn tại và `payment_date ≥ order_date`.
7. Nạp theo `updated_at`; chạy lại cùng batch không tạo duplicate.

## 4.5 Dirty batch chứa những loại lỗi nào?

Quan sát trực tiếp vài dòng đầu của `data/dirty/day_2026-07-02/` (danh sách đầy đủ – *Dirty Data Manifest* – chỉ giảng viên có):

| File | Ví dụ lỗi | Loại lỗi |
|---|---|---|
| customers | `email = not-an-email` | Business rule: email sai định dạng |
| customers | `CUS000003` dùng email của `CUS000002` | Unique: email trùng |
| products | `unit_price = -1000` | Business rule: giá âm |
| products | `category_id = CAT999` | Integrity: category không tồn tại |
| orders | `customer_id = CUS999999` | Integrity: khách không tồn tại |
| orders | `status = done` | Enum: trạng thái không hợp lệ |
| order_items | `quantity = 0` | Business rule: số lượng ≤ 0 |
| order_items | `product_id = PRD999999` | Integrity: sản phẩm không tồn tại |
| payments | `order_id = ORD999999` | Integrity: đơn không tồn tại |
| payments | `payment_status = paid` | Enum: trạng thái không hợp lệ |

Ngoài ra còn có thể có duplicate PK, sai kiểu dữ liệu, ngày không parse được, `payment_date < order_date`. Nhiệm vụ Buổi 7: **phát hiện và tách sang `data/reject/`**, không sửa file nguồn; bản ghi trùng PK mâu thuẫn thì quarantine, không tự chọn một bản.
