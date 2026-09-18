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
-- 1.2 Aggregate & Grouping — GROUP BY / HAVING (Q6-Q10)
-- Quy ước doanh thu: loại các đơn order_status = 'cancelled'.
-- Tháng tính theo giờ Việt Nam (Asia/Ho_Chi_Minh) vì order_date là timestamptz.
-- ============================================================

-- Q6: Tổng doanh thu theo từng tháng (DATE_TRUNC)
SELECT TO_CHAR(DATE_TRUNC('month', order_date AT TIME ZONE 'Asia/Ho_Chi_Minh'), 'YYYY-MM') AS order_month,
       COUNT(*)         AS order_count,
       SUM(order_total) AS total_revenue
FROM core.orders
WHERE order_status <> 'cancelled'
GROUP BY 1
ORDER BY 1;

-- Q7: Trung bình giá trị đơn hàng theo từng customer (AVG order_total GROUP BY customer_id)
SELECT customer_id,
       COUNT(*)                   AS order_count,
       ROUND(AVG(order_total), 2) AS avg_order_value
FROM core.orders
WHERE order_status <> 'cancelled'
GROUP BY customer_id
ORDER BY avg_order_value DESC, customer_id;

-- Q8: Số lượng đơn hàng theo từng order_status (tính cả cancelled)
SELECT order_status,
       COUNT(*) AS order_count
FROM core.orders
GROUP BY order_status
ORDER BY order_count DESC;

-- Q9: Tổng doanh thu theo category (order_items -> products -> categories)
-- Doanh thu dòng = quantity * unit_price - discount_amount
SELECT cat.category_id,
       cat.category_name,
       SUM(oi.quantity)                                        AS total_quantity,
       SUM(oi.quantity * oi.unit_price - oi.discount_amount)   AS total_revenue
FROM core.order_items oi
JOIN core.orders o       ON o.order_id = oi.order_id
JOIN core.products p     ON p.product_id = oi.product_id
JOIN core.categories cat ON cat.category_id = p.category_id
WHERE o.order_status <> 'cancelled'
GROUP BY cat.category_id, cat.category_name
ORDER BY total_revenue DESC;

-- Q10: HAVING — categories có tổng doanh thu > 1000
SELECT cat.category_id,
       cat.category_name,
       SUM(oi.quantity * oi.unit_price - oi.discount_amount) AS total_revenue
FROM core.order_items oi
JOIN core.orders o       ON o.order_id = oi.order_id
JOIN core.products p     ON p.product_id = oi.product_id
JOIN core.categories cat ON cat.category_id = p.category_id
WHERE o.order_status <> 'cancelled'
GROUP BY cat.category_id, cat.category_name
HAVING SUM(oi.quantity * oi.unit_price - oi.discount_amount) > 1000
ORDER BY total_revenue DESC;

-- ============================================================
-- 1.3 JOIN Operations (Q11-Q15)
-- Lưu ý: "price" trong đề = order_items.unit_price (giá tại thời điểm bán),
--        "total_amount" trong đề = orders.order_total.
-- ============================================================

-- Q11: Orders kèm customer_name, customer_email (orders JOIN customers)
SELECT o.order_id,
       o.order_date,
       o.order_status,
       o.order_total,
       c.full_name AS customer_name,
       c.email     AS customer_email
FROM core.orders o
JOIN core.customers c ON c.customer_id = o.customer_id
ORDER BY o.order_id;

-- Q12: Chi tiết từng order_item kèm product_name, price (order_items JOIN products)
-- sale_price = giá lúc bán (order_items.unit_price); list_price = giá niêm yết hiện tại (products.unit_price)
SELECT oi.order_item_id,
       oi.order_id,
       oi.product_id,
       p.product_name,
       oi.quantity,
       oi.unit_price                                  AS sale_price,
       p.unit_price                                   AS list_price,
       oi.discount_amount,
       oi.quantity * oi.unit_price - oi.discount_amount AS line_amount
FROM core.order_items oi
JOIN core.products p ON p.product_id = oi.product_id
ORDER BY oi.order_id, oi.order_item_id;

-- Q13: Orders có payments nhưng chưa có order_items (và ngược lại) — LEFT JOIN + IS NULL 1 phía
-- Chiều A: có payment, không có order_item | Chiều B: có order_item, không có payment
SELECT 'payment_no_items' AS mismatch_type, o.order_id, o.order_status, o.order_total
FROM core.orders o
JOIN (SELECT DISTINCT order_id FROM core.payments) pay ON pay.order_id = o.order_id
LEFT JOIN core.order_items oi ON oi.order_id = o.order_id
WHERE oi.order_item_id IS NULL
UNION ALL
SELECT 'items_no_payment' AS mismatch_type, o.order_id, o.order_status, o.order_total
FROM core.orders o
JOIN (SELECT DISTINCT order_id FROM core.order_items) itm ON itm.order_id = o.order_id
LEFT JOIN core.payments p ON p.order_id = o.order_id
WHERE p.payment_id IS NULL
ORDER BY mismatch_type, order_id;

-- Q14: Products chưa từng được bán (products LEFT JOIN order_items ... IS NULL)
SELECT p.product_id, p.product_name, p.category_id, p.unit_price, p.status
FROM core.products p
LEFT JOIN core.order_items oi ON oi.product_id = p.product_id
WHERE oi.order_item_id IS NULL
ORDER BY p.product_id;

-- Q15: Đối soát theo từng order: SUM(quantity*unit_price) so với orders.order_total
-- gross = SUM(quantity*unit_price); net = gross - SUM(discount_amount)
-- LEFT JOIN để đơn không có item vẫn xuất hiện (gross = 0 -> DIFF)
SELECT o.order_id,
       o.order_total,
       COALESCE(SUM(oi.quantity * oi.unit_price), 0)                        AS items_gross,
       COALESCE(SUM(oi.discount_amount), 0)                                 AS items_discount,
       COALESCE(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 0)   AS items_net,
       o.order_total - COALESCE(SUM(oi.quantity * oi.unit_price), 0)        AS diff_vs_gross,
       o.order_total - COALESCE(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 0) AS diff_vs_net,
       CASE WHEN o.order_total = COALESCE(SUM(oi.quantity * oi.unit_price - oi.discount_amount), 0)
            THEN 'MATCH' ELSE 'DIFF' END                                     AS recon_status
FROM core.orders o
LEFT JOIN core.order_items oi ON oi.order_id = o.order_id
GROUP BY o.order_id, o.order_total
ORDER BY o.order_id;

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
