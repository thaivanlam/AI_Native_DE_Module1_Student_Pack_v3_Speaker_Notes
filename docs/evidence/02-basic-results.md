# Minh chứng 02 — Basic Queries (SELECT / WHERE / ORDER BY)

- **File queries:** [sql/student/02_exercises_basic.sql](../../sql/student/02_exercises_basic.sql)
- **Container ID:** `62030a96c66be7d49f3e90b5e41dbadc752aa3a7e598a5ea37fbac6467759317` (`ecommerce-postgres`, image `postgres:16`)
- **Database:** `ecommerce`, schema `core`, user `de_user`
- **Thời điểm chạy:** 2026-09-18 16:12 +0700
- **Lệnh chạy:** `docker exec -i ecommerce-postgres psql -U de_user -d ecommerce -v ON_ERROR_STOP=1 < sql/student/02_exercises_basic.sql` → exit code 0 (không lỗi)

> Lưu ý: cột tiền trong `core.orders` là `order_total` (VND), tương ứng `total_amount` trong đề bài.
> Dữ liệu được load từ `data/seed/*.csv` (customers 1000, orders 5000, order_items 12717, payments 4517).

## Q1: SELECT with filtering — tất cả orders có tổng tiền (order_total) > 100

```sql
SELECT order_id, customer_id, order_date, order_status, order_total
FROM core.orders
WHERE order_total > 100
ORDER BY order_id;
```

**Kết quả** (5000 rows):

```text
 order_id  | customer_id |       order_date       | order_status | order_total 
-----------+-------------+------------------------+--------------+-------------
 ORD000001 | CUS000995   | 2026-06-12 05:35:00+00 | completed    |   700000.00
 ORD000002 | CUS000280   | 2026-03-07 07:15:00+00 | confirmed    |  2669000.00
 ORD000003 | CUS000659   | 2026-03-16 10:48:00+00 | shipped      | 10240000.00
 ORD000004 | CUS000192   | 2026-01-02 06:32:00+00 | completed    |   978000.00
 ORD000005 | CUS000814   | 2026-02-24 01:45:00+00 | completed    | 13361000.00
 ...       | ...         | ...                    | ...          | ...
(5000 rows)
```

## Q2: NULL handling — customers chưa có order nào (LEFT JOIN, giữ dòng không khớp orders)

```sql
SELECT c.customer_id, c.full_name, c.city, c.status
FROM core.customers c
LEFT JOIN core.orders o ON o.customer_id = c.customer_id
WHERE o.order_id IS NULL
ORDER BY c.customer_id;
```

**Kết quả** (6 rows):

```text
 customer_id |    full_name     |    city    | status 
-------------+------------------+------------+--------
 CUS000048   | Kelly York       | Vinh       | active
 CUS000282   | Joseph Snyder    | Hanoi      | active
 CUS000500   | Renee Warren     | Can Tho    | active
 CUS000595   | Richard Gonzalez | Hue        | active
 CUS000769   | Robert Montoya   | Quang Ninh | active
 CUS000974   | Austin King      | Nha Trang  | active
(6 rows)
```

## Q3: ORDER BY — top 10 customers theo tổng chi tiêu (SUM order_total từ bảng orders)

```sql
SELECT c.customer_id, c.full_name, COUNT(o.order_id) AS order_count, SUM(o.order_total) AS total_spent
FROM core.orders o
JOIN core.customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.full_name
ORDER BY total_spent DESC, c.customer_id
LIMIT 10;
```

**Kết quả** (10 rows):

```text
 customer_id |    full_name    | order_count | total_spent  
-------------+-----------------+-------------+--------------
 CUS000575   | Jessica Marquez |          15 | 209701000.00
 CUS000304   | Roberto Moon    |          12 | 191320000.00
 CUS000852   | Alfred Hubbard  |          12 | 187823500.00
 CUS000736   | Gordon Rogers   |          13 | 180159000.00
 CUS000305   | Lisa Patterson  |          12 | 177303000.00
 CUS000287   | Michele Dixon   |          13 | 176969500.00
 CUS000336   | Wayne Martinez  |          11 | 175471500.00
 CUS000646   | Ashley Small    |          10 | 166109500.00
 CUS000475   | Carla Lee       |           8 | 164104000.00
 CUS000271   | Cindy Blair     |          10 | 160608500.00
(10 rows)
```

## Q4: COUNT/DISTINCT — số customers khác nhau đã có ít nhất 1 đơn hàng

```sql
SELECT COUNT(DISTINCT customer_id) AS customers_with_orders
FROM core.orders;
```

**Kết quả** (1 row):

```text
 customers_with_orders 
-----------------------
                   994
(1 row)
```

## Q5: LIMIT — 5 orders mới nhất theo order_date

```sql
SELECT order_id, customer_id, order_date, order_status, order_total
FROM core.orders
ORDER BY order_date DESC
LIMIT 5;
```

**Kết quả** (5 rows):

```text
 order_id  | customer_id |       order_date       | order_status | order_total 
-----------+-------------+------------------------+--------------+-------------
 ORD000412 | CUS000573   | 2026-06-29 15:51:00+00 | completed    | 11847000.00
 ORD001049 | CUS000336   | 2026-06-29 15:38:00+00 | completed    | 17109000.00
 ORD004705 | CUS000262   | 2026-06-29 15:24:00+00 | completed    |  1790000.00
 ORD000417 | CUS000196   | 2026-06-29 13:46:00+00 | completed    | 20886000.00
 ORD002732 | CUS000408   | 2026-06-29 12:34:00+00 | completed    |  4012000.00
(5 rows)
```

## Đối soát với `data/seed/`

| Query | Database | Seed CSV (awk trên `data/seed/orders.csv`) | Khớp |
|-------|----------|--------------------------------------------|-------|
| Q1 — orders có `order_total > 100` | 5000 | 5000 | ✅ |
| Q2 — customers chưa có order | 6 | 1000 customers − 994 customers có order = 6 | ✅ |
| Q3 — top 1 customer | CUS000575 = 209,701,000.00 | CUS000575 = 209,701,000.00 | ✅ |
| Q4 — `COUNT(DISTINCT customer_id)` | 994 | 994 | ✅ |
| Q5 — order mới nhất | ORD000412 (2026-06-29 15:51 UTC) | giống | ✅ |

Nhận xét:
- Q1: mọi order đều > 100 VND nên ngưỡng 100 không lọc bớt dòng nào; giữ nguyên ngưỡng theo đề bài.
- Q2 + Q4 = 6 + 994 = 1000 = total customers → logic LEFT JOIN / IS NULL đúng.
- Q5: `order_date` là `timestamptz`, psql hiển thị theo UTC (+00): 15:51 UTC = 22:51 +07:00 trong file seed.
