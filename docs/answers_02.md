# 1.4 Business Questions — Đáp án

- **Nguồn dữ liệu:** PostgreSQL `ecommerce`, schema `core` (container `ecommerce-postgres`)
- **File SQL:** [`sql/student/02_exercises_basic.sql`](../sql/student/02_exercises_basic.sql) (mục 1.4, BQ1–BQ5)
- **Output chạy lại:** [`docs/evidence/02-business-results.txt`](evidence/02-business-results.txt)
- **Quy ước (theo [business_requirements.md](business_requirements.md)):** Total Revenue = doanh thu net của order `completed` = `SUM(orders.order_total)`. Cột `order_total` đã trừ `discount_amount`, đã đối soát khớp 5000/5000 đơn ở Q15. Tháng tính theo giờ `Asia/Ho_Chi_Minh`. Đơn vị tiền: VND.

## Tóm tắt

| # | Câu hỏi | Đáp án |
|---|---|---|
| 1 | Total revenue tháng 7/2026 | **0 VND** (core chưa có dữ liệu tháng 7) |
| 2 | Customer chi tiêu cao nhất | **CUS000736 – Gordon Rogers – 173,654,000 VND** |
| 3 | Category có nhiều orders nhất | **CAT012 – Skincare – 824 orders** |
| 4 | Average order value (AOV) | **12,391,222.68 VND** |
| 5 | Số customers có hơn 3 orders | **530 customers** |

---

## Câu 1. Total revenue tháng 7/2026 là bao nhiêu?

```sql
SELECT COUNT(*)                       AS completed_orders,
       COALESCE(SUM(order_total), 0)  AS total_revenue_2026_07
FROM core.orders
WHERE order_status = 'completed'
  AND order_date >= TIMESTAMPTZ '2026-07-01 00:00:00+07'
  AND order_date <  TIMESTAMPTZ '2026-08-01 00:00:00+07';
```

**Đáp án:** **0 VND** (0 order completed trong tháng 7/2026).

**Nhận xét:** `core.orders` hiện chỉ có đơn từ 01/01/2026 đến 29/06/2026 (giờ VN), nên doanh thu tháng 7 bằng 0 vì chưa nạp dữ liệu, không phải vì không bán được hàng. Dữ liệu tháng 7 đang nằm trong file incremental chưa nạp `data/incremental/day_2026-07-01/orders_daily.csv`, gồm 361 đơn completed, tổng 4,367,329,000 VND. Sau khi chạy pipeline incremental, chạy lại câu SQL này sẽ ra số thật. `COALESCE` giúp trả về 0 thay vì NULL khi tháng không có đơn.

---

## Câu 2. Customer nào có tổng chi tiêu cao nhất (id + tên + số tiền)?

```sql
SELECT c.customer_id,
       c.full_name,
       COUNT(*)           AS completed_orders,
       SUM(o.order_total) AS total_spent
FROM core.orders o
JOIN core.customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'completed'
GROUP BY c.customer_id, c.full_name
ORDER BY total_spent DESC, c.customer_id
LIMIT 1;
```

**Đáp án:** **CUS000736 – Gordon Rogers – 173,654,000 VND** (10 đơn completed).

**Nhận xét:** Kết quả phụ thuộc định nghĩa "chi tiêu". Nếu tính mọi đơn trừ `cancelled` thì top 1 là CUS000575 – Jessica Marquez (209,701,000 VND / 15 đơn). Tuy nhiên, phần lớn tiền của khách này nằm ở các đơn chưa hoàn tất. Chỉ đơn completed mới là tiền đã thực thu.

---

## Câu 3. Category nào có số lượng orders cao nhất?

```sql
SELECT cat.category_id,
       cat.category_name,
       COUNT(DISTINCT o.order_id) AS order_count
FROM core.order_items oi
JOIN core.orders o       ON o.order_id = oi.order_id
JOIN core.products p     ON p.product_id = oi.product_id
JOIN core.categories cat ON cat.category_id = p.category_id
WHERE o.order_status = 'completed'
GROUP BY cat.category_id, cat.category_name
ORDER BY order_count DESC, cat.category_id
LIMIT 1;
```

**Đáp án:** **CAT012 – Skincare – 824 orders** completed.

**Nhận xét:** Phải dùng `COUNT(DISTINCT order_id)` vì một đơn có thể có nhiều item cùng category. Một đơn cũng có thể chứa nhiều category, nên tổng theo các category sẽ lớn hơn tổng số đơn. Kitchen bám rất sát (813 đơn), và nếu tính mọi đơn trừ `cancelled` thì Kitchen vượt lên (999 so với 994). Hai category này gần như ngang nhau.

---

## Câu 4. Average order value (AOV) là bao nhiêu?

```sql
SELECT COUNT(*)                                AS completed_orders,
       SUM(order_total)                        AS total_revenue,
       ROUND(SUM(order_total) / COUNT(*), 2)   AS aov
FROM core.orders
WHERE order_status = 'completed';
```

**Đáp án:** **AOV = 12,391,222.68 VND** (48,077,944,000 VND / 3,880 đơn completed).

**Nhận xét:** AOV khoảng 12.4 triệu VND/đơn, khá cao, phù hợp với catalog có nhiều hàng giá trị lớn (Phones, Computers, Furniture). Nếu tính mọi đơn trừ `cancelled` thì AOV = 12,351,754.42 VND, chỉ chênh khoảng 0.3%, nên con số này ổn định.

---

## Câu 5. Có bao nhiêu customers có hơn 3 orders?

```sql
SELECT COUNT(*) AS customers_gt_3_orders
FROM (
    SELECT customer_id
    FROM core.orders
    WHERE order_status = 'completed'
    GROUP BY customer_id
    HAVING COUNT(*) > 3
) t;
```

**Đáp án:** **530 customers** có từ 4 đơn completed trở lên.

**Nhận xét:** Con số này chiếm khoảng 53% trong 994 khách đã từng đặt hàng, cho thấy tỷ lệ mua lại tốt. "Hơn 3" nghĩa là `> 3`, tức từ 4 đơn trở lên, không phải `>= 3`. Nếu đếm mọi đơn trừ `cancelled` thì ra 685, còn đếm tất cả đơn kể cả cancelled thì ra 719.
