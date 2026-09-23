-- ============================================================
-- Buổi 3 — 1.1 CTE Refactoring (CTE1 .. CTE5)
-- Schema: core (xem sql/student/01_create_oltp.sql)
-- Quy ước KPI (docs/business_requirements.md): spending / revenue = SUM(order_total)
--   của các order 'completed'. Tháng tính theo giờ Asia/Ho_Chi_Minh.
-- Mọi bước trung gian viết bằng WITH ... AS, không dùng subquery thay CTE.
-- ============================================================

-- CTE1: Top 10 customer theo total spending
-- CTE customer_spending gom SUM(order_total) mỗi customer; SELECT ngoài chỉ sắp xếp + lấy top 10.
WITH customer_spending AS (
    SELECT customer_id,
           COUNT(*)         AS order_count,
           SUM(order_total) AS total_spending
    FROM core.orders
    WHERE order_status = 'completed'
    GROUP BY customer_id
)
SELECT cs.customer_id,
       c.full_name,
       cs.order_count,
       cs.total_spending
FROM customer_spending cs
JOIN core.customers c ON c.customer_id = cs.customer_id
ORDER BY cs.total_spending DESC, cs.customer_id
LIMIT 10;

-- CTE2: Phân tầng spending Low / Medium / High
-- Ngưỡng đề bài Low < 500, Medium 500-2000, High > 2000 tính theo USD; dữ liệu là VND nên quy đổi
-- 1 USD = 25,000 VND -> Low < 12,500,000 | Medium 12,500,000-50,000,000 | High > 50,000,000.
-- Ngưỡng đặt trong CTE params để đổi một chỗ. LEFT JOIN từ customers để khách chưa có đơn
-- completed vẫn được tính (spending = 0 -> Low).
WITH params AS (
    SELECT 12500000::numeric AS low_max,
           50000000::numeric AS medium_max
),
customer_spending AS (
    SELECT c.customer_id,
           COALESCE(SUM(o.order_total), 0) AS total_spending
    FROM core.customers c
    LEFT JOIN core.orders o
           ON o.customer_id = c.customer_id
          AND o.order_status = 'completed'
    GROUP BY c.customer_id
),
customer_tier AS (
    SELECT cs.customer_id,
           cs.total_spending,
           CASE
               WHEN cs.total_spending <  p.low_max    THEN 'Low'
               WHEN cs.total_spending <= p.medium_max THEN 'Medium'
               ELSE 'High'
           END AS spending_tier
    FROM customer_spending cs
    CROSS JOIN params p
)
SELECT spending_tier,
       COUNT(*)                                            AS customer_count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)  AS customer_pct,
       MIN(total_spending)                                 AS min_spending,
       MAX(total_spending)                                 AS max_spending,
       ROUND(AVG(total_spending), 2)                       AS avg_spending
FROM customer_tier
GROUP BY spending_tier
ORDER BY MIN(total_spending);

-- CTE3: Nested CTEs — orders_per_customer -> customer_stats
-- CTE thứ 2 đọc từ CTE thứ 1: đếm số order completed mỗi customer, rồi tính MIN/MAX/AVG
-- và phân bố số order trên toàn bộ tập customer.
WITH orders_per_customer AS (
    SELECT customer_id,
           COUNT(*) AS order_count
    FROM core.orders
    WHERE order_status = 'completed'
    GROUP BY customer_id
),
customer_stats AS (
    SELECT COUNT(*)                                                     AS customer_count,
           MIN(order_count)                                             AS min_orders,
           MAX(order_count)                                             AS max_orders,
           ROUND(AVG(order_count), 2)                                   AS avg_orders,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY order_count)     AS median_orders,
           COUNT(*) FILTER (WHERE order_count = 1)                      AS one_time_customers
    FROM orders_per_customer
)
SELECT customer_count,
       min_orders,
       max_orders,
       avg_orders,
       median_orders,
       one_time_customers,
       ROUND(100.0 * one_time_customers / customer_count, 2) AS one_time_pct
FROM customer_stats;

-- CTE4: AOV (Average Order Value) mỗi customer = total_spending / order_count
-- NULLIF chống chia 0 (an toàn dù CTE chỉ chứa customer có >= 1 order).
WITH customer_orders AS (
    SELECT customer_id,
           COUNT(*)         AS order_count,
           SUM(order_total) AS total_spending
    FROM core.orders
    WHERE order_status = 'completed'
    GROUP BY customer_id
),
customer_aov AS (
    SELECT customer_id,
           order_count,
           total_spending,
           ROUND(total_spending / NULLIF(order_count, 0), 2) AS aov
    FROM customer_orders
)
SELECT customer_id,
       order_count,
       total_spending,
       aov
FROM customer_aov
ORDER BY aov DESC, customer_id;

-- CTE5: (TODO) Retention — CTE cohort (tháng order đầu) + CTE orders tháng sau, tính % quay lại.
