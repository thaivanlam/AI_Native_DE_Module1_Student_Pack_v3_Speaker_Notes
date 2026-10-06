# 2.2 Performance Testing — OLTP vs Data Mart

- **Môi trường:** PostgreSQL 16.15, container `ecommerce-postgres`, db `ecommerce`, user `de_user` (Docker Desktop trên máy cá nhân).
- **Dữ liệu:** `core.orders` 5,000 dòng · `core.order_items` 12,717 dòng · `mart.fact_sales` 12,717 dòng · 500 sản phẩm · 180 ngày.
- **Cách đo:** `EXPLAIN (ANALYZE, BUFFERS)`, mỗi câu chạy 1 lần làm nóng cache rồi đo **9 lần**, lấy **median** của `Execution Time`. Mọi lần đọc đều là `shared hit` (dữ liệu nằm sẵn trong bộ nhớ, không có I/O đĩa).
- **Quy ước KPI:** doanh thu net của đơn `completed`, tháng theo giờ `Asia/Ho_Chi_Minh` — hai câu trả về cùng 90 dòng kết quả.

## Kết luận

Với KPI nhiều JOIN (**revenue theo tháng × category**), mart nhanh hơn OLTP khoảng **1.6 lần theo median** (18.97 ms so với 31.17 ms) và **1.4 lần theo lần chạy nhanh nhất** (18.47 ms so với 25.85 ms). Dữ liệu còn nhỏ nên mức chênh tuyệt đối chỉ khoảng 7–12 ms; phần JOIN của mart nhanh gấp ~2.7 lần, nhưng bước sắp xếp cho `COUNT(DISTINCT)` chiếm phần lớn thời gian ở cả hai phía nên kéo tỉ lệ tổng lại gần nhau.

Mart **không** nhanh hơn trong mọi trường hợp: với KPI chỉ cần mức đơn hàng (revenue theo tháng, không chia category), OLTP nhanh hơn mart khoảng 5 lần — xem [mục 4](#4-trường-hợp-ngược-lại-kpi-ở-mức-đơn-hàng).

## 1. Câu SQL

**OLTP — 3 JOIN trên schema `core`, tự tính revenue và tự quy đổi múi giờ:**

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT to_char(o.order_date AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYY-MM') AS order_month,
       c.category_name                                        AS category,
       COUNT(DISTINCT o.order_id)                             AS completed_orders,
       SUM(oi.quantity * oi.unit_price - oi.discount_amount)  AS total_revenue
FROM core.order_items oi
JOIN core.orders o      ON o.order_id = oi.order_id
JOIN core.products p    ON p.product_id = oi.product_id
JOIN core.categories c  ON c.category_id = p.category_id
WHERE o.order_status = 'completed'
GROUP BY 1, 2
ORDER BY 1, 2;
```

**Mart — star join trên schema `mart`, revenue và tháng đã tính sẵn lúc load:**

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT d.year_month               AS order_month,
       p.category,
       COUNT(DISTINCT f.order_id) AS completed_orders,
       SUM(f.revenue)             AS total_revenue
FROM mart.fact_sales f
JOIN mart.dim_date d         ON d.date_key = f.date_key
JOIN mart.dim_product p      ON p.product_key = f.product_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY 1, 2
ORDER BY 1, 2;
```

## 2. Output EXPLAIN ANALYZE

Mỗi khối dưới đây là lần chạy có `Execution Time` đúng bằng median của 9 lần đo.

**OLTP:**

```text
GroupAggregate  (cost=1310.12..1680.17 rows=9868 width=330) (actual time=25.801..31.022 rows=90 loops=1)
  Group Key: (to_char((o.order_date AT TIME ZONE 'Asia/Ho_Chi_Minh'::text), 'YYYY-MM'::text)), c.category_name
  Buffers: shared hit=260
  ->  Sort  (cost=1310.12..1334.79 rows=9868 width=314) (actual time=25.689..26.360 rows=9933 loops=1)
        Sort Key: (to_char((o.order_date AT TIME ZONE 'Asia/Ho_Chi_Minh'::text), 'YYYY-MM'::text)), c.category_name, o.order_id
        Sort Method: quicksort  Memory: 1062kB
        Buffers: shared hit=260
        ->  Hash Join  (cost=222.97..655.45 rows=9868 width=314) (actual time=1.328..10.182 rows=9933 loops=1)
              Hash Cond: ((p.category_id)::text = (c.category_id)::text)
              Buffers: shared hit=257
              ->  Hash Join  (cost=208.25..564.96 rows=9868 width=39) (actual time=1.141..5.710 rows=9933 loops=1)
                    Hash Cond: ((oi.product_id)::text = (p.product_id)::text)
                    Buffers: shared hit=256
                    ->  Hash Join  (cost=189.00..519.59 rows=9868 width=42) (actual time=1.038..4.263 rows=9933 loops=1)
                          Hash Cond: ((oi.order_id)::text = (o.order_id)::text)
                          Buffers: shared hit=248
                          ->  Seq Scan on order_items oi  (cost=0.00..297.17 rows=12717 width=34) (actual time=0.004..0.867 rows=12717 loops=1)
                                Buffers: shared hit=170
                          ->  Hash  (cost=140.50..140.50 rows=3880 width=18) (actual time=1.015..1.016 rows=3880 loops=1)
                                Buckets: 4096  Batches: 1  Memory Usage: 222kB
                                Buffers: shared hit=78
                                ->  Seq Scan on orders o  (cost=0.00..140.50 rows=3880 width=18) (actual time=0.003..0.548 rows=3880 loops=1)
                                      Filter: ((order_status)::text = 'completed'::text)
                                      Rows Removed by Filter: 1120
                                      Buffers: shared hit=78
                    ->  Hash  (cost=13.00..13.00 rows=500 width=17) (actual time=0.094..0.095 rows=500 loops=1)
                          Buckets: 1024  Batches: 1  Memory Usage: 32kB
                          Buffers: shared hit=8
                          ->  Seq Scan on products p  (cost=0.00..13.00 rows=500 width=17) (actual time=0.002..0.045 rows=500 loops=1)
                                Buffers: shared hit=8
              ->  Hash  (cost=12.10..12.10 rows=210 width=296) (actual time=0.012..0.012 rows=20 loops=1)
                    Buckets: 1024  Batches: 1  Memory Usage: 9kB
                    Buffers: shared hit=1
                    ->  Seq Scan on categories c  (cost=0.00..12.10 rows=210 width=296) (actual time=0.006..0.007 rows=20 loops=1)
                          Buffers: shared hit=1
Planning:
  Buffers: shared hit=307
Planning Time: 0.800 ms
Execution Time: 31.168 ms
```

**Mart:**

```text
GroupAggregate  (cost=455.97..488.88 rows=90 width=57) (actual time=17.020..18.820 rows=90 loops=1)
  Group Key: d.year_month, p.category
  Buffers: shared hit=209
  ->  Sort  (cost=455.97..462.33 rows=2543 width=33) (actual time=16.963..17.344 rows=9933 loops=1)
        Sort Key: d.year_month, p.category, f.order_id
        Sort Method: quicksort  Memory: 981kB
        Buffers: shared hit=209
        ->  Hash Join  (cost=57.29..312.14 rows=2543 width=33) (actual time=0.282..3.756 rows=9933 loops=1)
              Hash Cond: (f.product_key = p.product_key)
              Buffers: shared hit=203
              ->  Hash Join  (cost=38.04..286.15 rows=2543 width=28) (actual time=0.182..2.734 rows=9933 loops=1)
                    Hash Cond: (f.date_key = d.date_key)
                    Buffers: shared hit=195
                    ->  Nested Loop  (cost=31.99..273.27 rows=2543 width=24) (actual time=0.142..1.755 rows=9933 loops=1)
                          Buffers: shared hit=193
                          ->  Seq Scan on dim_order_status s  (cost=0.00..1.06 rows=1 width=4) (actual time=0.003..0.007 rows=1 loops=1)
                                Filter: ((order_status)::text = 'completed'::text)
                                Rows Removed by Filter: 4
                                Buffers: shared hit=1
                          ->  Bitmap Heap Scan on fact_sales f  (cost=31.99..246.78 rows=2543 width=28) (actual time=0.138..0.902 rows=9933 loops=1)
                                Recheck Cond: (order_status_key = s.order_status_key)
                                Heap Blocks: exact=183
                                Buffers: shared hit=192
                                ->  Bitmap Index Scan on idx_fact_sales_order_status  (cost=0.00..31.36 rows=2543 width=0) (actual time=0.122..0.122 rows=9933 loops=1)
                                      Index Cond: (order_status_key = s.order_status_key)
                                      Buffers: shared hit=9
                    ->  Hash  (cost=3.80..3.80 rows=180 width=12) (actual time=0.031..0.032 rows=180 loops=1)
                          Buckets: 1024  Batches: 1  Memory Usage: 16kB
                          Buffers: shared hit=2
                          ->  Seq Scan on dim_date d  (cost=0.00..3.80 rows=180 width=12) (actual time=0.002..0.013 rows=180 loops=1)
                                Buffers: shared hit=2
              ->  Hash  (cost=13.00..13.00 rows=500 width=13) (actual time=0.092..0.092 rows=500 loops=1)
                    Buckets: 1024  Batches: 1  Memory Usage: 31kB
                    Buffers: shared hit=8
                    ->  Seq Scan on dim_product p  (cost=0.00..13.00 rows=500 width=13) (actual time=0.005..0.040 rows=500 loops=1)
                          Buffers: shared hit=8
Planning:
  Buffers: shared hit=467
Planning Time: 0.856 ms
Execution Time: 18.966 ms
```

## 3. Bảng so sánh

| Chỉ số | OLTP (`core`) | Mart (`mart`) | Chênh lệch |
|---|---|---|---|
| Execution Time — median 9 lần | **31.17 ms** | **18.97 ms** | mart nhanh hơn 1.64× (−12.2 ms) |
| Execution Time — nhanh nhất | 25.85 ms | 18.47 ms | mart nhanh hơn 1.40× (−7.4 ms) |
| Execution Time — chậm nhất | 45.81 ms | 20.69 ms | OLTP dao động mạnh hơn |
| Planning Time (lần median) | 0.800 ms | 0.856 ms | tương đương |
| Thời điểm JOIN xong (trước Sort) | ~10.2 ms | ~3.8 ms | mart nhanh hơn ~2.7× |
| Buffers đọc khi thực thi | 260 trang | 209 trang | mart đọc ít hơn ~20% |
| Số dòng kết quả | 90 | 90 | giống nhau |

Số "JOIN xong" và "Buffers" lấy từ plan (dòng `actual time` của Hash Join trên cùng và dòng `Buffers` của node gốc).

**Vì sao mart nhanh hơn ở phần JOIN:**

- **Khoá JOIN là số nguyên.** Mart nối bằng `INTEGER` surrogate key; OLTP nối bằng `VARCHAR` (`order_id`, `product_id`, `category_id`), phải băm và so sánh chuỗi.
- **Không phải tính lại.** `revenue` và `year_month` đã có sẵn trong mart; OLTP phải tính `quantity * unit_price - discount_amount` và `to_char(... AT TIME ZONE ...)` cho từng dòng.
- **Lọc sớm bằng index.** Mart dùng `idx_fact_sales_order_status` (Bitmap Index Scan) để chỉ lấy 9,933 dòng `completed`; OLTP phải quét toàn bộ `order_items` (12,717 dòng) rồi mới loại khi JOIN với `orders`.
- **Category đã gộp vào `dim_product`**, nên mart bớt được một bảng (`categories`) so với OLTP.

**Vì sao tổng thời gian chỉ chênh ~1.4–1.6×:** ở cả hai plan, bước `Sort` 9,933 dòng theo (tháng, category, `order_id`) để phục vụ `COUNT(DISTINCT order_id)` tốn khoảng 13–16 ms, tức từ một nửa thời gian trở lên. Bước này giống nhau ở hai phía nên mart không rút ngắn được.

## 4. Trường hợp ngược lại: KPI ở mức đơn hàng

Đề gợi ý KPI "revenue by month". Với KPI này OLTP không cần JOIN nào vì `orders.order_total` đã là doanh thu net của cả đơn:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT to_char(order_date AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYY-MM') AS order_month,
       COUNT(*)         AS completed_orders,
       SUM(order_total) AS total_revenue
FROM core.orders
WHERE order_status = 'completed'
GROUP BY 1
ORDER BY 1;
```

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT d.year_month               AS order_month,
       COUNT(DISTINCT f.order_id) AS completed_orders,
       SUM(f.revenue)             AS total_revenue
FROM mart.fact_sales f
JOIN mart.dim_date d         ON d.date_key = f.date_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY 1
ORDER BY 1;
```

| Chỉ số | OLTP (`core`) | Mart (`mart`) |
|---|---|---|
| Execution Time — median 9 lần | **3.01 ms** | **16.30 ms** |
| Execution Time — nhanh nhất | 2.93 ms | 14.35 ms |

Ở đây mart **chậm hơn khoảng 5 lần**. Lý do là grain: fact ở mức dòng hàng (12,717 dòng) nên phải JOIN 2 dimension và `COUNT(DISTINCT order_id)` để đếm đơn, còn OLTP chỉ đọc 3,880 dòng `completed` của một bảng đã ở đúng mức đơn hàng. Star schema có lợi khi câu hỏi cần cắt theo nhiều chiều (product, category, segment…); với KPI cố định ở mức thô hơn grain, cách tăng tốc đúng là bảng tổng hợp sẵn (`monthly_summary` — phương án (b) của mục 2.1), không phải fact chi tiết.

## 5. Index

Fact đã có index trên cả 5 cột FK và `order_id` (tạo ở mục 1.1), và plan của mart đang dùng `idx_fact_sales_order_status`.

Tôi thử thêm một covering index để đọc thẳng từ index, không vào bảng:

```sql
CREATE INDEX idx_tmp_cover ON mart.fact_sales(order_status_key)
  INCLUDE (date_key, product_key, order_id, revenue);
```

Planner chuyển sang `Index Only Scan`, nhưng `Execution Time` nhanh nhất vẫn là 18.30 ms so với 18.47 ms khi chưa có index — không cải thiện đáng kể, vì thời gian nằm ở bước `Sort` chứ không ở bước quét. Thử nghiệm chạy trong transaction và đã `ROLLBACK`, **không giữ lại index này**.

## 6. Nhận xét

- Với 12,717 dòng, mọi câu đều dưới 50 ms và dữ liệu nằm trọn trong bộ nhớ, nên các con số trên chỉ cho thấy **xu hướng**; sai số giữa các lần chạy (OLTP: 25.9–45.8 ms) cùng cỡ với mức chênh giữa hai phía.
- Lợi thế của mart sẽ rõ hơn khi dữ liệu lớn: khoá số nguyên và dòng fact hẹp giúp hash join và quét bảng rẻ hơn, và khi fact đủ lớn có thể partition theo `date_key`.
- Lợi ích không đo được bằng ms: câu mart ngắn hơn, không phải nhớ công thức revenue hay quy tắc múi giờ, nên ít rủi ro viết sai KPI hơn.
