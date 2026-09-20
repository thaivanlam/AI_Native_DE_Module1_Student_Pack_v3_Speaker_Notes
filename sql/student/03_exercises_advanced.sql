-- Buổi 3
-- TODO 1: Refactor business report bằng CTE nhiều bước.
-- TODO 2: Running revenue theo ngày.
-- TODO 3: DENSE_RANK product trong từng category.
-- TODO 4: first_purchase, recency, frequency, monetary.
-- TODO 5: cohort_month × activity_month.

-- ============================================================
-- Bonus 2.1 — Advanced Analytics (Window Functions)
-- Schema: core (xem sql/student/01_create_oltp.sql)
-- Quy ước KPI (docs/business_requirements.md): revenue = SUM(order_total) của
--   order 'completed'; doanh thu theo category = SUM(quantity*unit_price - discount_amount)
--   của các dòng order_items thuộc đơn 'completed'.
-- Tháng tính theo giờ Việt Nam (Asia/Ho_Chi_Minh) vì order_date là timestamptz.
-- ============================================================

-- Bonus 2.1 — B1: Cumulative revenue theo tháng
-- SUM(...) OVER (ORDER BY month) = running total: mặc định frame RANGE BETWEEN
-- UNBOUNDED PRECEDING AND CURRENT ROW -> cộng dồn từ tháng đầu tiên tới tháng hiện tại.
WITH monthly AS (
    SELECT DATE_TRUNC('month', order_date AT TIME ZONE 'Asia/Ho_Chi_Minh') AS month_start,
           COUNT(*)         AS order_count,
           SUM(order_total) AS monthly_revenue
    FROM core.orders
    WHERE order_status = 'completed'
    GROUP BY 1
)
SELECT TO_CHAR(month_start, 'YYYY-MM')                      AS order_month,
       order_count,
       monthly_revenue,
       SUM(monthly_revenue) OVER (ORDER BY month_start)     AS cumulative_revenue,
       ROUND(100.0 * SUM(monthly_revenue) OVER (ORDER BY month_start)
                   / SUM(monthly_revenue) OVER (), 2)       AS cumulative_pct
FROM monthly
ORDER BY month_start;

-- Bonus 2.1 — B2: Tỷ trọng doanh thu từng category
-- SUM(...) OVER () không có PARTITION/ORDER BY -> tổng toàn bộ kết quả trên mỗi dòng,
-- dùng làm mẫu số để tính % mà không cần self-join hay subquery tổng.
WITH cat_rev AS (
    SELECT cat.category_id,
           cat.category_name,
           SUM(oi.quantity * oi.unit_price - oi.discount_amount) AS category_revenue
    FROM core.order_items oi
    JOIN core.orders o       ON o.order_id = oi.order_id
    JOIN core.products p     ON p.product_id = oi.product_id
    JOIN core.categories cat ON cat.category_id = p.category_id
    WHERE o.order_status = 'completed'
    GROUP BY cat.category_id, cat.category_name
)
SELECT category_id,
       category_name,
       category_revenue,
       ROUND(100.0 * category_revenue / SUM(category_revenue) OVER (), 2) AS revenue_pct,
       ROUND(100.0 * SUM(category_revenue) OVER (ORDER BY category_revenue DESC, category_id)
                   / SUM(category_revenue) OVER (), 2)                    AS cumulative_pct,
       RANK() OVER (ORDER BY category_revenue DESC)                       AS revenue_rank
FROM cat_rev
ORDER BY category_revenue DESC, category_id;

-- Bonus 2.1 — B3: Customers "churn" — không có order trong 30 ngày gần nhất
-- Mốc so sánh là MAX(order_date) của toàn bộ dataset (không dùng NOW()) vì dữ liệu
-- là snapshot lịch sử; cutoff = MAX(order_date) - INTERVAL '30 days'.
-- Chỉ xét khách đã từng đặt hàng; khách chưa có đơn nào xem ở Q2 (02_exercises_basic.sql).
WITH bound AS (
    SELECT MAX(order_date) AS last_order_overall FROM core.orders
),
last_per_customer AS (
    SELECT o.customer_id,
           MAX(o.order_date) AS last_order_date,
           COUNT(*)          AS order_count,
           SUM(o.order_total) FILTER (WHERE o.order_status = 'completed') AS lifetime_revenue
    FROM core.orders o
    GROUP BY o.customer_id
)
SELECT c.customer_id,
       c.full_name,
       c.city,
       c.customer_segment,
       lpc.order_count,
       COALESCE(lpc.lifetime_revenue, 0) AS lifetime_revenue,
       lpc.last_order_date AT TIME ZONE 'Asia/Ho_Chi_Minh' AS last_order_vn,
       (b.last_order_overall::date - lpc.last_order_date::date) AS days_since_last_order
FROM last_per_customer lpc
JOIN core.customers c ON c.customer_id = lpc.customer_id
CROSS JOIN bound b
WHERE lpc.last_order_date < b.last_order_overall - INTERVAL '30 days'
ORDER BY days_since_last_order DESC, lifetime_revenue DESC, c.customer_id;
