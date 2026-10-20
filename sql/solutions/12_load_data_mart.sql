-- B8 / Bai 4: incremental Sales Data Mart, one row per order_item.
-- Execute in a caller-managed transaction (no TRUNCATE or internal COMMIT).
CREATE SCHEMA IF NOT EXISTS mart;

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

CREATE TABLE IF NOT EXISTS mart.dim_customer (
  customer_key SERIAL PRIMARY KEY,
  customer_id VARCHAR(12) NOT NULL UNIQUE,
  full_name VARCHAR(150) NOT NULL,
  city VARCHAR(100) NOT NULL DEFAULT 'Unknown',
  customer_segment VARCHAR(30) NOT NULL,
  status VARCHAR(20) NOT NULL
);

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

CREATE TABLE IF NOT EXISTS mart.dim_payment_method (
  payment_method_key SERIAL PRIMARY KEY,
  payment_method VARCHAR(30) NOT NULL UNIQUE,
  payment_method_name VARCHAR(50) NOT NULL,
  is_digital BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS mart.dim_order_status (
  order_status_key SERIAL PRIMARY KEY,
  order_status VARCHAR(20) NOT NULL UNIQUE,
  status_name VARCHAR(50) NOT NULL,
  status_order INTEGER NOT NULL,
  is_final BOOLEAN NOT NULL
);

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

CREATE INDEX IF NOT EXISTS idx_fact_sales_date ON mart.fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer ON mart.fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product ON mart.fact_sales(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_payment_method ON mart.fact_sales(payment_method_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_order_status ON mart.fact_sales(order_status_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_order ON mart.fact_sales(order_id);


-- Keep existing Buoi 4 revenue queries compatible; net_amount is the same measure.
ALTER TABLE mart.fact_sales ADD COLUMN IF NOT EXISTS net_amount NUMERIC(12,2)
  GENERATED ALWAYS AS (revenue) STORED;

INSERT INTO mart.dim_date
  (date_key, full_date, day, month, month_name, quarter, year, year_month,
   day_of_week, day_name, is_weekend)
SELECT to_char(d, 'YYYYMMDD')::int, d::date, EXTRACT(DAY FROM d),
       EXTRACT(MONTH FROM d), to_char(d, 'FMMonth'), EXTRACT(QUARTER FROM d),
       EXTRACT(YEAR FROM d), to_char(d, 'YYYY-MM'), EXTRACT(ISODOW FROM d),
       to_char(d, 'FMDay'), EXTRACT(ISODOW FROM d) IN (6, 7)
FROM generate_series(DATE '2025-01-01', DATE '2027-12-31', INTERVAL '1 day') AS d
ON CONFLICT (date_key) DO NOTHING;

INSERT INTO mart.dim_customer (customer_id, full_name, city, customer_segment, status)
SELECT customer_id, full_name, COALESCE(city, 'Unknown'), customer_segment, status
FROM core.customers
ON CONFLICT (customer_id) DO UPDATE SET
  full_name = EXCLUDED.full_name, city = EXCLUDED.city,
  customer_segment = EXCLUDED.customer_segment, status = EXCLUDED.status;

-- The optional Buoi 4 bonus replaces UNIQUE(product_id) with SCD2 keys.
-- Keep that history instead of restoring the Type 1 unique constraint.
DO $$
BEGIN
IF EXISTS (
  SELECT 1 FROM information_schema.columns
  WHERE table_schema = 'mart' AND table_name = 'dim_product'
    AND column_name = 'is_current'
) THEN
  -- Follow the bonus exercise's day-grain effective dates. Multiple changes
  -- on the same day update that day's version rather than create an invalid range.
  UPDATE mart.dim_product d
  SET valid_to = (p.updated_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - 1,
      is_current = FALSE
  FROM core.products p
  WHERE p.product_id = d.product_id AND d.is_current
    AND (d.list_price, d.cost_price, d.category_id)
        IS DISTINCT FROM (p.unit_price, p.cost_price, p.category_id)
    AND (p.updated_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date > d.valid_from;

  INSERT INTO mart.dim_product
    (product_id, product_name, category_id, category, parent_category,
     list_price, cost_price, status, valid_from, valid_to, is_current)
  SELECT p.product_id, p.product_name, p.category_id, c.category_name,
         COALESCE(pc.category_name, c.category_name), p.unit_price, p.cost_price, p.status,
         CASE WHEN EXISTS (SELECT 1 FROM mart.dim_product old WHERE old.product_id = p.product_id)
              THEN (p.updated_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
              ELSE DATE '1900-01-01' END,
         DATE '9999-12-31', TRUE
  FROM core.products p
  JOIN core.categories c ON c.category_id = p.category_id
  LEFT JOIN core.categories pc ON pc.category_id = c.parent_category_id
  WHERE NOT EXISTS (SELECT 1 FROM mart.dim_product d
                    WHERE d.product_id = p.product_id AND d.is_current);

  UPDATE mart.dim_product d
  SET product_name = p.product_name, category_id = p.category_id,
      category = c.category_name, parent_category = COALESCE(pc.category_name, c.category_name),
      list_price = p.unit_price, cost_price = p.cost_price, status = p.status
  FROM core.products p
  JOIN core.categories c ON c.category_id = p.category_id
  LEFT JOIN core.categories pc ON pc.category_id = c.parent_category_id
  WHERE d.product_id = p.product_id AND d.is_current
    AND (p.updated_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date >= d.valid_from;
ELSE
INSERT INTO mart.dim_product
  (product_id, product_name, category_id, category, parent_category,
   list_price, cost_price, status)
SELECT p.product_id, p.product_name, p.category_id, c.category_name,
       COALESCE(pc.category_name, c.category_name), p.unit_price, p.cost_price, p.status
FROM core.products p
JOIN core.categories c ON c.category_id = p.category_id
LEFT JOIN core.categories pc ON pc.category_id = c.parent_category_id
ON CONFLICT (product_id) DO UPDATE SET
  product_name = EXCLUDED.product_name, category_id = EXCLUDED.category_id,
  category = EXCLUDED.category, parent_category = EXCLUDED.parent_category,
  list_price = EXCLUDED.list_price, cost_price = EXCLUDED.cost_price,
  status = EXCLUDED.status;
END IF;
END $$;

INSERT INTO mart.dim_payment_method
  (payment_method_key, payment_method, payment_method_name, is_digital)
VALUES (0, 'unknown', 'Unknown', FALSE)
ON CONFLICT (payment_method) DO NOTHING;

INSERT INTO mart.dim_payment_method (payment_method, payment_method_name, is_digital)
SELECT payment_method, INITCAP(REPLACE(payment_method, '_', ' ')), payment_method <> 'cash'
FROM (SELECT DISTINCT payment_method FROM core.payments) m
ON CONFLICT (payment_method) DO UPDATE SET
  payment_method_name = EXCLUDED.payment_method_name, is_digital = EXCLUDED.is_digital;

INSERT INTO mart.dim_order_status (order_status, status_name, status_order, is_final)
SELECT order_status, status_name, status_order, is_final FROM core.order_status
ON CONFLICT (order_status) DO UPDATE SET
  status_name = EXCLUDED.status_name, status_order = EXCLUDED.status_order,
  is_final = EXCLUDED.is_final;

-- Refuse to silently omit facts whose source dates fall outside the calendar.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM core.order_items oi JOIN core.orders o USING (order_id)
    LEFT JOIN mart.dim_date d ON d.date_key =
      to_char(o.order_date AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYYMMDD')::int
    WHERE d.date_key IS NULL
  ) THEN
    RAISE EXCEPTION 'Order date outside mart.dim_date calendar';
  END IF;
END $$;

WITH order_payment AS (
  SELECT DISTINCT ON (order_id) order_id, payment_method
  FROM core.payments WHERE payment_status = 'success'
  ORDER BY order_id, payment_date DESC, payment_id DESC
)
INSERT INTO mart.fact_sales
  (date_key, customer_key, product_key, payment_method_key, order_status_key,
   order_id, order_item_id, channel, quantity, unit_price, discount, gross_amount, revenue)
SELECT to_char(o.order_date AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYYMMDD')::int,
       dc.customer_key, dp.product_key, dpm.payment_method_key, dos.order_status_key,
       o.order_id, oi.order_item_id, o.channel, oi.quantity, oi.unit_price,
       oi.discount_amount, oi.quantity * oi.unit_price,
       oi.quantity * oi.unit_price - oi.discount_amount
FROM core.order_items oi
JOIN core.orders o ON o.order_id = oi.order_id
JOIN mart.dim_customer dc ON dc.customer_id = o.customer_id
JOIN mart.dim_product dp ON dp.product_id = oi.product_id
 AND (o.order_date AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
     BETWEEN COALESCE((to_jsonb(dp)->>'valid_from')::date, DATE '1900-01-01')
         AND COALESCE((to_jsonb(dp)->>'valid_to')::date, DATE '9999-12-31')
JOIN mart.dim_order_status dos ON dos.order_status = o.order_status
LEFT JOIN order_payment op ON op.order_id = o.order_id
JOIN mart.dim_payment_method dpm ON dpm.payment_method = COALESCE(op.payment_method, 'unknown')
ON CONFLICT (order_item_id) DO NOTHING;
