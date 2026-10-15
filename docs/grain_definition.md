# Định nghĩa hạt dữ liệu (Grain Definition)

Grain trả lời một câu hỏi: **một dòng của bảng này đại diện cho cái gì?**
Tài liệu này chốt grain cho từng bảng của pipeline `API -> RAW -> core -> mart`.

## Tuyên bố grain

Mức chi tiết nhất của dự án là **dòng hàng**: 1 dòng `mart.fact_sales` = 1 `order_item`,
tức 1 sản phẩm trong 1 đơn hàng, của 1 khách, vào 1 ngày đặt hàng.

Grain này lấy nguyên từ `core.order_items`, bảng chi tiết nhất của nguồn. Từ đây cộng dồn
lên đơn hàng, ngày, tháng, danh mục hay khách hàng đều được; đi theo chiều ngược lại thì không.

Hệ quả: thuộc tính cấp đơn (khách, ngày, trạng thái, kênh, phương thức thanh toán) lặp lại
trên mọi dòng hàng của đơn. Đếm đơn phải dùng `COUNT(DISTINCT order_id)`, không dùng `COUNT(*)`.

## Grain theo từng tầng

### RAW (`data/raw/<run_id>/<resource>.json`)

| Đối tượng | 1 đơn vị = | Khóa grain |
|---|---|---|
| File | 1 resource trong 1 lần chạy | `run_id` + `resource` |
| Phần tử trong `data` | 1 bản ghi API trả về tại lần chạy đó | `run_id` + `resource` + ID bản ghi |

RAW là bất biến (ghi bằng mode `x`), nên cùng một `order_id` có thể xuất hiện ở nhiều `run_id`.
Mỗi lần xuất hiện là một ảnh chụp trạng thái tại thời điểm fetch, không phải dòng trùng.

### Core / OLTP (schema `core`)

Mỗi bảng giữ **trạng thái mới nhất** của một thực thể, 1 dòng cho mỗi ID.

| Bảng | 1 dòng = | Khóa grain (PK) | Số dòng seed |
|---|---|---|---|
| `core.customers` | 1 khách hàng | `customer_id` | 1.000 |
| `core.categories` | 1 danh mục | `category_id` | |
| `core.products` | 1 sản phẩm | `product_id` | 500 |
| `core.order_status` | 1 trạng thái đơn | `order_status` | 5 |
| `core.orders` | 1 đơn hàng | `order_id` | 5.000 |
| `core.order_items` | 1 sản phẩm trong 1 đơn | `order_item_id` | 12.717 |
| `core.payments` | 1 giao dịch thanh toán | `payment_id` | 4.517 |

Quan hệ làm thay đổi grain khi JOIN:

- `customers` 1:N `orders`
- `orders` 1:N `order_items`
- `products` 1:N `order_items`
- `orders` 1:N `payments` (một đơn có 0..n giao dịch: thất bại rồi thành công, hoàn tiền)

### Mart (schema `mart`)

| Bảng | 1 dòng = | Khóa grain | Số dòng (06/10/2026) |
|---|---|---|---|
| `mart.fact_sales` | 1 `order_item` | `order_item_id` (UNIQUE) | 12.717 |
| `mart.dim_date` | 1 ngày lịch | `date_key` (YYYYMMDD) | 180 |
| `mart.dim_customer` | 1 khách hàng | `customer_id` | 1.000 |
| `mart.dim_product` | 1 sản phẩm | `product_id` | 500 |
| `mart.dim_payment_method` | 1 phương thức thanh toán | `payment_method` | 5 |
| `mart.dim_order_status` | 1 trạng thái đơn | `order_status` | 5 |

Hai điểm cần lưu ý:

- `sales_key`, `customer_key`, `product_key`... là surrogate key. Chúng là PK kỹ thuật,
  không định nghĩa grain; cột định nghĩa grain là natural key ở bảng trên.
- Nếu chạy thêm `sql/student/04_bonus_scd.sql`, grain của `dim_product` đổi thành
  **1 phiên bản của 1 sản phẩm**, khóa `(product_id, valid_from)`, và mỗi `product_id`
  có đúng 1 dòng `is_current`.

## Khóa grain và tính duy nhất

Khóa grain được bảo vệ ở cả hai tầng database, không dựa vào code:

- **Core:** `src/load_postgres.py` upsert bằng `ON CONFLICT (<pk>) DO UPDATE` với đúng
  các PK trong bảng trên. Load lại cùng một bản ghi sẽ cập nhật dòng cũ, không thêm dòng mới.
  Đây là lý do pipeline idempotent (xem [idempotency_test.md](idempotency_test.md)).
- **Mart:** `fact_sales.order_item_id` có ràng buộc `UNIQUE`. Script load `TRUNCATE` rồi
  `INSERT` lại trong một transaction, nên chạy lại không nhân đôi dòng.

Phép JOIN duy nhất có nguy cơ phá grain khi load fact là `orders -> payments` (1:N).
Script xử lý bằng CTE `order_payment`: mỗi đơn chỉ lấy 1 payment `success` mới nhất
(`DISTINCT ON (order_id)`); đơn chưa có payment thành công được gán về `unknown`.

## Cái gì không phải grain

| Mức dễ nhầm | Vì sao không chọn | Hệ quả nếu nhầm |
|---|---|---|
| 1 dòng = 1 đơn hàng | Đơn nhiều sản phẩm không chia được doanh thu về từng product/category | Không trả lời được revenue theo danh mục |
| 1 dòng = 1 khách hàng theo ngày | Đã là mức tổng hợp, mất chi tiết đơn và sản phẩm | Không drill-down được, không tính được AOV |
| 1 dòng = 1 giao dịch thanh toán | Một đơn có 0..n payment | Dòng hàng bị nhân theo số payment, revenue đội lên |

Quy tắc khi viết query trên `fact_sales`:

- `quantity`, `gross_amount`, `discount`, `revenue` cộng dồn được theo mọi dimension.
- `unit_price` không cộng dồn được; không `SUM`.
- Không `SUM(orders.order_total)` sau khi JOIN sang `order_items`: giá trị cấp đơn bị lặp
  theo số dòng hàng. Dùng `SUM(fact_sales.revenue)` thay thế.

## Kiểm tra grain

Chạy sau mỗi lần load mart. Cả ba câu phải trả về kết quả như ghi chú.

```sql
-- 1. Không có khóa grain trùng: phải trả về 0 dòng.
SELECT order_item_id, COUNT(*)
FROM mart.fact_sales
GROUP BY order_item_id
HAVING COUNT(*) > 1;

-- 2. Fact giữ đúng grain của nguồn: diff phải bằng 0.
SELECT (SELECT COUNT(*) FROM mart.fact_sales)
     - (SELECT COUNT(*) FROM core.order_items) AS diff;

-- 3. Roll-up lên đơn hàng không mất, không thừa đơn: diff phải bằng 0.
SELECT (SELECT COUNT(DISTINCT order_id) FROM mart.fact_sales)
     - (SELECT COUNT(*) FROM core.orders) AS diff;
```

Kết quả đối soát gần nhất: 12.717/12.717 dòng hàng của 5.000/5.000 đơn, chênh lệch revenue
bằng 0 (xem [evidence/04-rowcounts.txt](evidence/04-rowcounts.txt)).

## Giả định và câu hỏi mở

- Ngày của một dòng fact là ngày **đặt hàng** theo giờ `Asia/Ho_Chi_Minh`, không phải ngày
  thanh toán hay ngày giao.
- Mart nạp mọi trạng thái đơn, kể cả `cancelled`. Lọc trạng thái là việc của câu KPI.
- `src/transform.py` chưa có bước loại bản ghi trùng ID trong cùng một lô. Hiện PK của
  `core` đảm nhận việc này (bản ghi sau ghi đè bản ghi trước). Cần quyết định có thêm bước
  dedup tường minh ở staging hay không.
- Số dòng `core` ở trên là số seed; sau các lần load incremental từ API con số thực tế sẽ lớn hơn.
