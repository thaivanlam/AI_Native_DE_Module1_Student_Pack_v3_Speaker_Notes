-- 04_kpi_from_mart.sql
-- Buoi 4 - 1.4 KPI Queries: 5 KPI chi doc tu schema mart (fact_sales JOIN dims),
-- KHONG JOIN bang OLTP (schema core).
--
-- Quy uoc (theo docs/business_requirements.md, giong cac bai Buoi 2-3):
--   - Revenue = doanh thu NET cua don 'completed' = SUM(fact_sales.revenue),
--     loc trang thai qua dim_order_status (mart nap tat ca trang thai don).
--   - Grain cua fact la order_item -> dem don phai dung COUNT(DISTINCT order_id).
--   - Ngay/thang da duoc quy ve gio Asia/Ho_Chi_Minh luc load (dim_date).
--   - Don vi tien: VND.
-- Ket qua: docs/evidence/04-kpi-results.txt, dap an: docs/answers_04.md

-- KPI1: Total revenue by month (dim_date.month)
SELECT d.year,
       d.month,
       d.month_name,
       COUNT(DISTINCT f.order_id) AS completed_orders,
       SUM(f.revenue)             AS total_revenue
FROM mart.fact_sales f
JOIN mart.dim_date d ON d.date_key = f.date_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- KPI2: Revenue by category (qua dim_product.category)
-- revenue_pct = ty trong tren tong revenue cua don completed.
SELECT p.parent_category,
       p.category,
       SUM(f.quantity)            AS units_sold,
       SUM(f.revenue)             AS total_revenue,
       ROUND(100.0 * SUM(f.revenue) / SUM(SUM(f.revenue)) OVER (), 2) AS revenue_pct
FROM mart.fact_sales f
JOIN mart.dim_product p ON p.product_key = f.product_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY p.parent_category, p.category
ORDER BY total_revenue DESC, p.category;

-- KPI3: Top 10 products theo revenue
SELECT p.product_id,
       p.product_name,
       p.category,
       SUM(f.quantity) AS units_sold,
       SUM(f.revenue)  AS total_revenue
FROM mart.fact_sales f
JOIN mart.dim_product p ON p.product_key = f.product_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY p.product_id, p.product_name, p.category
ORDER BY total_revenue DESC, p.product_id
LIMIT 10;

-- KPI4: AOV = SUM(revenue) / COUNT(DISTINCT order_id)
SELECT SUM(f.revenue)             AS total_revenue,
       COUNT(DISTINCT f.order_id) AS completed_orders,
       ROUND(SUM(f.revenue) / COUNT(DISTINCT f.order_id), 2) AS aov
FROM mart.fact_sales f
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed';

-- KPI5: Customer count by segment (dim_customer.customer_segment)
-- Dem khach hang CO don completed (COUNT DISTINCT vi 1 khach co nhieu dong fact).
SELECT c.customer_segment,
       COUNT(DISTINCT f.customer_key) AS customer_count,
       COUNT(DISTINCT f.order_id)     AS completed_orders,
       SUM(f.revenue)                 AS total_revenue,
       ROUND(SUM(f.revenue) / COUNT(DISTINCT f.customer_key), 2) AS revenue_per_customer
FROM mart.fact_sales f
JOIN mart.dim_customer c ON c.customer_key = f.customer_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY c.customer_segment
ORDER BY total_revenue DESC;

-- KPI5b: Customer count by region (dim_customer.city) - mart co ca segment lan
-- city nen lam them chieu region.
SELECT c.city,
       COUNT(DISTINCT f.customer_key) AS customer_count,
       COUNT(DISTINCT f.order_id)     AS completed_orders,
       SUM(f.revenue)                 AS total_revenue
FROM mart.fact_sales f
JOIN mart.dim_customer c ON c.customer_key = f.customer_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY c.city
ORDER BY customer_count DESC, c.city;
