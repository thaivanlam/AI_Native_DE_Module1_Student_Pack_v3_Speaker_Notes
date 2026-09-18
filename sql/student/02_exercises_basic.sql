-- ============================================================
-- 1.1 Basic Queries — SELECT / WHERE / ORDER BY
-- Schema: core (xem sql/student/01_create_oltp.sql)
-- Lưu ý: cột tiền trong core.orders là order_total (VND), tương ứng "total_amount" trong đề.
-- ============================================================

-- Q1: SELECT with filtering — tất cả orders có tổng tiền (order_total) > 100
SELECT order_id, customer_id, order_date, order_status, order_total
FROM core.orders
WHERE order_total > 100
ORDER BY order_id;

-- Q2: NULL handling — customers chưa có order nào (LEFT JOIN, giữ dòng không khớp orders)
SELECT c.customer_id, c.full_name, c.city, c.status
FROM core.customers c
LEFT JOIN core.orders o ON o.customer_id = c.customer_id
WHERE o.order_id IS NULL
ORDER BY c.customer_id;

-- Q3: ORDER BY — top 10 customers theo tổng chi tiêu (SUM order_total từ bảng orders)
SELECT c.customer_id, c.full_name, COUNT(o.order_id) AS order_count, SUM(o.order_total) AS total_spent
FROM core.orders o
JOIN core.customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.full_name
ORDER BY total_spent DESC, c.customer_id
LIMIT 10;

-- Q4: COUNT/DISTINCT — số customers khác nhau đã có ít nhất 1 đơn hàng
SELECT COUNT(DISTINCT customer_id) AS customers_with_orders
FROM core.orders;

-- Q5: LIMIT — 5 orders mới nhất theo order_date
SELECT order_id, customer_id, order_date, order_status, order_total
FROM core.orders
ORDER BY order_date DESC
LIMIT 5;

-- ============================================================
-- Buổi 2: 10 business questions
-- TODO 1: Tổng số khách hàng active theo city
-- TODO 2: Top 10 sản phẩm có unit_price cao nhất
-- TODO 3: Số đơn theo ngày và status
-- TODO 4: Revenue/AOV của completed orders theo tháng
-- TODO 5: Revenue theo category
-- TODO 6: Top 10 customers theo revenue
-- TODO 7: Top 10 products theo quantity
-- TODO 8: Payment success rate
-- TODO 9: Revenue theo channel
-- TODO 10: Đối soát SUM(order_total) với tổng item net amount
