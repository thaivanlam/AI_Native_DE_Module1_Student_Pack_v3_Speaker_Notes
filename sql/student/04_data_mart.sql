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
--   date_key           = to_char(orders.order_date, 'YYYYMMDD')::int
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

-- TODO: Script load (-- LOAD ...) tu core sang mart.
-- TODO: Viết 5 query đối soát OLTP ↔ Data Mart.
