-- 04_data_mart.sql
-- Buoi 4: Sales Data Mart (star schema) trong schema mart, nguon la schema core (OLTP).
--
-- =====================================================================
-- GRAIN: one row per order_item (1 dong fact = 1 dong hang trong 1 don hang)
-- =====================================================================
--   Tuc la: 1 san pham, trong 1 don, cua 1 khach, vao 1 ngay dat hang.
--   Vi sao chon grain nay:
--   - La muc chi tiet nhat cua nguon (core.order_items) -> khong mat thong tin,
--     roll-up len don hang / ngay / thang / category / khach hang deu duoc.
--   - Revenue theo product/category chi tinh dung o muc dong hang; neu grain la
--     order thi 1 don nhieu san pham khong chia duoc doanh thu ve tung category.
--   - Cac measure (quantity, revenue, discount) deu cong don duoc (additive)
--     theo moi dimension o grain nay.
--   He qua: thuoc tinh cap don (customer, ngay, status, payment method) lap lai
--   tren moi dong hang cua don; dem so don phai dung COUNT(DISTINCT order_id).
--
-- =====================================================================
-- STAR SCHEMA (dimension 1 ---< n fact)
-- =====================================================================
--   dim_date           1 ---< n fact_sales (date_key)
--   dim_customer       1 ---< n fact_sales (customer_key)
--   dim_product        1 ---< n fact_sales (product_key)
--   dim_payment_method 1 ---< n fact_sales (payment_method_key)
--   dim_order_status   1 ---< n fact_sales (order_status_key)
--
-- Thu tu tao bang: 5 dimension truoc, fact_sales sau (fact tham chieu FK toi dim).
--
-- Quy uoc khoa:
--   - dim_date dung smart key INTEGER dang YYYYMMDD: doc duoc bang mat, tinh
--     duoc truc tiep tu order_date khi load fact, khong can lookup.
--   - 4 dim con lai dung surrogate key SERIAL lam PK, giu natural key cua OLTP
--     (customer_id, product_id, ...) lam cot UNIQUE de lookup khi load.
--     Ly do: khoa so nguyen JOIN nhanh hon VARCHAR, tach mart khoi khoa nguon,
--     va san sang cho SCD Type 2 (1 natural key co nhieu phien ban).
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS mart;

-- dim_date: lich, 1 dong = 1 ngay.
-- Nguon: khong co bang OLTP tuong ung; sinh bang generate_series tu
--   MIN(order_date) den MAX(order_date) cua core.orders.
-- Map: date_key = to_char(full_date, 'YYYYMMDD')::int; cac cot con lai EXTRACT tu full_date.
-- Business: tach san nam/quy/thang/thu de GROUP BY khong phai goi ham ngay thang
--   tren fact; day_of_week theo ISO (1 = thu Hai ... 7 = Chu nhat).
CREATE TABLE IF NOT EXISTS mart.dim_date (
  date_key INTEGER PRIMARY KEY,
  full_date DATE NOT NULL UNIQUE,
  day SMALLINT NOT NULL CHECK (day BETWEEN 1 AND 31),
  month SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
  month_name VARCHAR(10) NOT NULL,
  quarter SMALLINT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
  year SMALLINT NOT NULL,
  year_month CHAR(7) NOT NULL,
  day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
  day_name VARCHAR(10) NOT NULL,
  is_weekend BOOLEAN NOT NULL
);

-- dim_customer: 1 dong = 1 khach hang.
-- Nguon: core.customers.
-- Map: customer_id, full_name, city, customer_segment, status lay nguyen;
--   city NULL -> 'Unknown' de GROUP BY khong ra nhom NULL.
-- Business: phuc vu phan tich theo segment / city. Khong mang email, phone sang
--   mart (PII, khong can cho bao cao). SCD Type 1: ghi de khi khach doi thong tin.
CREATE TABLE IF NOT EXISTS mart.dim_customer (
  customer_key SERIAL PRIMARY KEY,
  customer_id VARCHAR(12) NOT NULL UNIQUE,
  full_name VARCHAR(150) NOT NULL,
  city VARCHAR(100) NOT NULL DEFAULT 'Unknown',
  customer_segment VARCHAR(30) NOT NULL,
  status VARCHAR(20) NOT NULL
);

-- dim_product: 1 dong = 1 san pham, da gop san thong tin danh muc (denormalize).
-- Nguon: core.products JOIN core.categories (va self-join lay danh muc cha).
-- Map: category = categories.category_name;
--   parent_category = category_name cua parent_category_id, danh muc goc -> lay chinh no;
--   list_price = products.unit_price (gia niem yet HIEN TAI), cost_price lay nguyen.
-- Business: revenue theo category chi can JOIN fact -> dim_product (khong can
--   them bang categories). Gia ban thuc te nam o fact_sales.unit_price, khong
--   phai list_price.
CREATE TABLE IF NOT EXISTS mart.dim_product (
  product_key SERIAL PRIMARY KEY,
  product_id VARCHAR(12) NOT NULL UNIQUE,
  product_name VARCHAR(200) NOT NULL,
  category_id VARCHAR(10) NOT NULL,
  category VARCHAR(120) NOT NULL,
  parent_category VARCHAR(120) NOT NULL,
  list_price NUMERIC(12,2) NOT NULL CHECK (list_price >= 0),
  cost_price NUMERIC(12,2) NOT NULL CHECK (cost_price >= 0),
  status VARCHAR(20) NOT NULL
);

-- dim_payment_method: 1 dong = 1 phuong thuc thanh toan.
-- Nguon: SELECT DISTINCT payment_method FROM core.payments
--   (cash, bank_transfer, card, e_wallet) + 1 dong 'unknown' (payment_method_key = 0).
-- Map: payment_method_name = ten hien thi; is_digital = FALSE voi cash va unknown.
-- Business: core.payments o grain giao dich (1 don co 0..n payment), fact o grain
--   dong hang -> moi don chi gan 1 phuong thuc: payment 'success' moi nhat cua don.
--   Don chua co payment thanh cong tro ve dong 'unknown' de FK o fact luon NOT NULL
--   va INNER JOIN khong lam roi dong.
CREATE TABLE IF NOT EXISTS mart.dim_payment_method (
  payment_method_key SERIAL PRIMARY KEY,
  payment_method VARCHAR(30) NOT NULL UNIQUE,
  payment_method_name VARCHAR(50) NOT NULL,
  is_digital BOOLEAN NOT NULL
);

-- dim_order_status: 1 dong = 1 trang thai don hang.
-- Nguon: core.order_status (bang lookup).
-- Map: order_status, status_name, status_order, is_final lay nguyen.
-- Business: loc KPI theo trang thai (vd revenue chi tinh don 'completed', loai
--   'cancelled'); status_order de sap xep theo vong doi don hang.
CREATE TABLE IF NOT EXISTS mart.dim_order_status (
  order_status_key SERIAL PRIMARY KEY,
  order_status VARCHAR(20) NOT NULL UNIQUE,
  status_name VARCHAR(50) NOT NULL,
  status_order INTEGER NOT NULL,
  is_final BOOLEAN NOT NULL
);

-- fact_sales: 1 dong = 1 order_item (xem GRAIN dau file).
-- Nguon: core.order_items JOIN core.orders (+ core.payments de chon phuong thuc).
-- Map FK:
--   date_key           = to_char(orders.order_date AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYYMMDD')::int
--                        (order_date la timestamptz -> quy ve ngay theo gio Viet Nam)
--   customer_key       = lookup dim_customer theo orders.customer_id
--   product_key        = lookup dim_product theo order_items.product_id
--   order_status_key   = lookup dim_order_status theo orders.order_status
--   payment_method_key = lookup dim_payment_method theo payment 'success' moi nhat, khong co -> 0
-- Map measures:
--   quantity, unit_price = order_items (unit_price la gia TAI THOI DIEM BAN)
--   discount     = order_items.discount_amount
--   gross_amount = quantity * unit_price
--   revenue      = gross_amount - discount (doanh thu thuan cua dong hang)
-- Degenerate dimensions (khong co bang dim rieng): order_id de dem don / tinh AOV,
--   order_item_id de truy vet ve nguon va chong load trung (UNIQUE = dung grain),
--   channel la thuoc tinh cap don chi co 3 gia tri.
-- Luu y: unit_price la non-additive (khong SUM), cac measure con lai additive.
CREATE TABLE IF NOT EXISTS mart.fact_sales (
  sales_key BIGSERIAL PRIMARY KEY,
  date_key INTEGER NOT NULL REFERENCES mart.dim_date(date_key),
  customer_key INTEGER NOT NULL REFERENCES mart.dim_customer(customer_key),
  product_key INTEGER NOT NULL REFERENCES mart.dim_product(product_key),
  payment_method_key INTEGER NOT NULL REFERENCES mart.dim_payment_method(payment_method_key),
  order_status_key INTEGER NOT NULL REFERENCES mart.dim_order_status(order_status_key),
  order_id VARCHAR(12) NOT NULL,
  order_item_id VARCHAR(16) NOT NULL UNIQUE,
  channel VARCHAR(20) NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
  discount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
  gross_amount NUMERIC(12,2) NOT NULL CHECK (gross_amount >= 0),
  revenue NUMERIC(12,2) NOT NULL CHECK (revenue >= 0),
  CONSTRAINT fact_sales_amount_check
    CHECK (gross_amount = quantity * unit_price AND revenue = gross_amount - discount)
);

-- Index tren cac cot FK cua fact (PostgreSQL khong tu tao index cho FK) de tang
-- toc star join va loc theo dimension; order_id cho COUNT(DISTINCT) / drill-down theo don.
CREATE INDEX IF NOT EXISTS idx_fact_sales_date ON mart.fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer ON mart.fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product ON mart.fact_sales(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_payment_method ON mart.fact_sales(payment_method_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_order_status ON mart.fact_sales(order_status_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_order ON mart.fact_sales(order_id);

-- =====================================================================
-- LOAD: nap du lieu tu core (OLTP) sang mart
-- =====================================================================
-- Chien luoc: full refresh, idempotent = TRUNCATE toan bo roi INSERT lai trong
--   1 transaction (chay lai nhieu lan khong nhan doi dong; loi giua chung thi
--   ROLLBACK, mart giu nguyen trang thai cu). RESTART IDENTITY de surrogate key
--   danh so lai tu 1 moi lan refresh.
-- Thu tu: 5 dimension truoc, fact_sales sau (fact lookup surrogate key tu dim).
-- Quy uoc ngay: order_date la timestamptz -> quy ve ngay theo gio Asia/Ho_Chi_Minh,
--   cung quy uoc voi cac bai Buoi 2-3.
BEGIN;

TRUNCATE mart.fact_sales, mart.dim_date, mart.dim_customer, mart.dim_product,
         mart.dim_payment_method, mart.dim_order_status RESTART IDENTITY;

-- LOAD 1: dim_date - sinh lich lien tuc tu ngay dat hang nho nhat den lon nhat.
-- generate_series tao ca nhung ngay khong co don -> bao cao theo ngay khong bi thung.
INSERT INTO mart.dim_date
  (date_key, full_date, day, month, month_name, quarter, year, year_month,
   day_of_week, day_name, is_weekend)
SELECT to_char(d, 'YYYYMMDD')::int,
       d::date,
       EXTRACT(DAY FROM d),
       EXTRACT(MONTH FROM d),
       to_char(d, 'FMMonth'),
       EXTRACT(QUARTER FROM d),
       EXTRACT(YEAR FROM d),
       to_char(d, 'YYYY-MM'),
       EXTRACT(ISODOW FROM d),
       to_char(d, 'FMDay'),
       EXTRACT(ISODOW FROM d) IN (6, 7)
FROM (
  SELECT MIN(order_date AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS min_date,
         MAX(order_date AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS max_date
  FROM core.orders
) r
CROSS JOIN LATERAL generate_series(r.min_date, r.max_date, INTERVAL '1 day') AS d
ORDER BY d;

-- LOAD 2: dim_customer - toan bo khach hang (ke ca khach chua co don).
INSERT INTO mart.dim_customer (customer_id, full_name, city, customer_segment, status)
SELECT customer_id, full_name, COALESCE(city, 'Unknown'), customer_segment, status
FROM core.customers
ORDER BY customer_id;

-- LOAD 3: dim_product - gop ten danh muc va danh muc cha vao san pham.
-- LEFT JOIN danh muc cha: danh muc goc (parent NULL) -> parent_category = chinh no.
INSERT INTO mart.dim_product
  (product_id, product_name, category_id, category, parent_category,
   list_price, cost_price, status)
SELECT p.product_id, p.product_name, p.category_id, c.category_name,
       COALESCE(pc.category_name, c.category_name),
       p.unit_price, p.cost_price, p.status
FROM core.products p
JOIN core.categories c ON c.category_id = p.category_id
LEFT JOIN core.categories pc ON pc.category_id = c.parent_category_id
ORDER BY p.product_id;

-- LOAD 4: dim_payment_method - dong 'unknown' (key 0) cho don chua co payment
-- thanh cong, sau do la cac phuong thuc thuc te xuat hien trong core.payments.
INSERT INTO mart.dim_payment_method
  (payment_method_key, payment_method, payment_method_name, is_digital)
VALUES (0, 'unknown', 'Unknown', FALSE);

INSERT INTO mart.dim_payment_method (payment_method, payment_method_name, is_digital)
SELECT payment_method,
       INITCAP(REPLACE(payment_method, '_', ' ')),
       payment_method <> 'cash'
FROM (SELECT DISTINCT payment_method FROM core.payments) m
ORDER BY payment_method;

-- LOAD 5: dim_order_status - copy bang lookup, sap theo vong doi don hang.
INSERT INTO mart.dim_order_status (order_status, status_name, status_order, is_final)
SELECT order_status, status_name, status_order, is_final
FROM core.order_status
ORDER BY status_order;

-- LOAD 6: fact_sales - 1 dong cho moi core.order_items (dung grain).
-- JOIN: order_items -> orders -> products -> payments, roi lookup surrogate key o cac dim.
-- CTE order_payment: moi don chi lay 1 payment 'success' moi nhat (DISTINCT ON) de
--   JOIN voi payments khong nhan doi dong hang; don khong co payment thanh cong ->
--   LEFT JOIN ra NULL -> COALESCE ve 'unknown'.
-- Nap TAT CA trang thai don (ke ca cancelled): loc theo trang thai la viec cua
--   cau KPI thong qua dim_order_status, khong phai cua buoc load.
WITH order_payment AS (
  SELECT DISTINCT ON (order_id) order_id, payment_method
  FROM core.payments
  WHERE payment_status = 'success'
  ORDER BY order_id, payment_date DESC, payment_id DESC
)
INSERT INTO mart.fact_sales
  (date_key, customer_key, product_key, payment_method_key, order_status_key,
   order_id, order_item_id, channel,
   quantity, unit_price, discount, gross_amount, revenue)
SELECT to_char(o.order_date AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYYMMDD')::int,
       dc.customer_key,
       dp.product_key,
       dpm.payment_method_key,
       dos.order_status_key,
       o.order_id,
       oi.order_item_id,
       o.channel,
       oi.quantity,
       oi.unit_price,
       oi.discount_amount,
       oi.quantity * oi.unit_price,
       oi.quantity * oi.unit_price - oi.discount_amount
FROM core.order_items oi
JOIN core.orders o ON o.order_id = oi.order_id
JOIN core.products p ON p.product_id = oi.product_id
LEFT JOIN order_payment op ON op.order_id = o.order_id
JOIN mart.dim_customer dc ON dc.customer_id = o.customer_id
JOIN mart.dim_product dp ON dp.product_id = p.product_id
JOIN mart.dim_order_status dos ON dos.order_status = o.order_status
JOIN mart.dim_payment_method dpm
  ON dpm.payment_method = COALESCE(op.payment_method, 'unknown')
ORDER BY o.order_date, oi.order_item_id;

COMMIT;

-- Cap nhat thong ke cho planner sau khi nap lai toan bo.
ANALYZE mart.dim_date;
ANALYZE mart.dim_customer;
ANALYZE mart.dim_product;
ANALYZE mart.dim_payment_method;
ANALYZE mart.dim_order_status;
ANALYZE mart.fact_sales;

-- =====================================================================
-- VERIFY: row counts + doi soat OLTP <-> Data Mart
-- =====================================================================
-- Ket qua luu tai docs/evidence/04-rowcounts.txt.

-- V0: so dong tung bang mart, dat canh so dong nguon ky vong.
SELECT 'dim_date' AS mart_table,
       (SELECT COUNT(*) FROM mart.dim_date) AS mart_rows,
       (SELECT MAX(order_date AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
             - MIN(order_date AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + 1
        FROM core.orders) AS expected_rows,
       'so ngay tu MIN den MAX(order_date)' AS expected_from
UNION ALL
SELECT 'dim_customer', (SELECT COUNT(*) FROM mart.dim_customer),
       (SELECT COUNT(*) FROM core.customers), 'core.customers'
UNION ALL
SELECT 'dim_product', (SELECT COUNT(*) FROM mart.dim_product),
       (SELECT COUNT(*) FROM core.products), 'core.products'
UNION ALL
SELECT 'dim_payment_method', (SELECT COUNT(*) FROM mart.dim_payment_method),
       (SELECT COUNT(DISTINCT payment_method) + 1 FROM core.payments),
       'DISTINCT core.payments.payment_method + 1 dong unknown'
UNION ALL
SELECT 'dim_order_status', (SELECT COUNT(*) FROM mart.dim_order_status),
       (SELECT COUNT(*) FROM core.order_status), 'core.order_status'
UNION ALL
SELECT 'fact_sales', (SELECT COUNT(*) FROM mart.fact_sales),
       (SELECT COUNT(*) FROM core.order_items), 'core.order_items';

-- V1: tong revenue - SUM(fact.revenue) vs SUM(orders.order_total), tat ca trang thai.
SELECT o.oltp_revenue, m.mart_revenue, m.mart_revenue - o.oltp_revenue AS diff
FROM (SELECT SUM(order_total) AS oltp_revenue FROM core.orders) o
CROSS JOIN (SELECT SUM(revenue) AS mart_revenue FROM mart.fact_sales) m;

-- V2: so don hang - COUNT(DISTINCT order_id) o fact vs so dong core.orders.
SELECT o.oltp_orders, m.mart_orders, m.mart_orders - o.oltp_orders AS diff
FROM (SELECT COUNT(*) AS oltp_orders FROM core.orders) o
CROSS JOIN (SELECT COUNT(DISTINCT order_id) AS mart_orders FROM mart.fact_sales) m;

-- V3: gross va discount - bac cau giai thich revenue = gross - discount.
SELECT o.oltp_gross, m.mart_gross, o.oltp_discount, m.mart_discount,
       m.mart_gross - m.mart_discount AS mart_gross_minus_discount
FROM (SELECT SUM(quantity * unit_price) AS oltp_gross,
             SUM(discount_amount) AS oltp_discount
      FROM core.order_items) o
CROSS JOIN (SELECT SUM(gross_amount) AS mart_gross, SUM(discount) AS mart_discount
            FROM mart.fact_sales) m;

-- V4: revenue theo thang (gio Viet Nam) - kiem tra map date_key.
SELECT COALESCE(o.order_month, m.order_month) AS order_month,
       o.oltp_revenue, m.mart_revenue,
       COALESCE(m.mart_revenue, 0) - COALESCE(o.oltp_revenue, 0) AS diff
FROM (SELECT to_char(order_date AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYY-MM') AS order_month,
             SUM(order_total) AS oltp_revenue
      FROM core.orders
      GROUP BY 1) o
FULL JOIN (SELECT d.year_month AS order_month, SUM(f.revenue) AS mart_revenue
           FROM mart.fact_sales f
           JOIN mart.dim_date d ON d.date_key = f.date_key
           GROUP BY 1) m ON m.order_month = o.order_month
ORDER BY 1;

-- V5: revenue theo trang thai don - kiem tra map order_status_key.
SELECT COALESCE(o.order_status, m.order_status) AS order_status,
       o.oltp_orders, m.mart_orders, o.oltp_revenue, m.mart_revenue,
       COALESCE(m.mart_revenue, 0) - COALESCE(o.oltp_revenue, 0) AS diff
FROM (SELECT order_status, COUNT(*) AS oltp_orders, SUM(order_total) AS oltp_revenue
      FROM core.orders
      GROUP BY 1) o
FULL JOIN (SELECT s.order_status, COUNT(DISTINCT f.order_id) AS mart_orders,
                  SUM(f.revenue) AS mart_revenue
           FROM mart.fact_sales f
           JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
           GROUP BY 1) m ON m.order_status = o.order_status
ORDER BY 1;

-- V6: phuong thuc thanh toan - so don theo phuong thuc o mart vs payment 'success'
-- o OLTP; nhom 'unknown' phai bang so don khong co payment thanh cong.
SELECT COALESCE(o.payment_method, m.payment_method) AS payment_method,
       o.oltp_orders, m.mart_orders,
       COALESCE(m.mart_orders, 0) - COALESCE(o.oltp_orders, 0) AS diff
FROM (SELECT COALESCE(p.payment_method, 'unknown') AS payment_method,
             COUNT(DISTINCT o.order_id) AS oltp_orders
      FROM core.orders o
      LEFT JOIN core.payments p
        ON p.order_id = o.order_id AND p.payment_status = 'success'
      GROUP BY 1) o
FULL JOIN (SELECT pm.payment_method, COUNT(DISTINCT f.order_id) AS mart_orders
           FROM mart.fact_sales f
           JOIN mart.dim_payment_method pm
             ON pm.payment_method_key = f.payment_method_key
           GROUP BY 1) m ON m.payment_method = o.payment_method
ORDER BY 1;
