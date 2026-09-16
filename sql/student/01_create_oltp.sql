-- 01_create_oltp.sql
-- DDL cho lop OLTP (schema core), dong bo voi database/ecommerce_oltp.dbml
CREATE SCHEMA IF NOT EXISTS core;
SET search_path TO core, public;

CREATE TABLE IF NOT EXISTS categories (
  category_id VARCHAR(10) PRIMARY KEY,
  category_name VARCHAR(120) NOT NULL,
  parent_category_id VARCHAR(10),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT categories_parent_category_id_fkey
    FOREIGN KEY (parent_category_id) REFERENCES categories(category_id)
);

CREATE TABLE IF NOT EXISTS customers (
  customer_id VARCHAR(12) PRIMARY KEY,
  full_name VARCHAR(150) NOT NULL,
  email VARCHAR(200) NOT NULL UNIQUE,
  phone VARCHAR(30),
  city VARCHAR(100),
  customer_segment VARCHAR(30) NOT NULL,
  status VARCHAR(20) NOT NULL CHECK (status IN ('active','inactive')),
  source_system VARCHAR(50) NOT NULL DEFAULT 'unknown',
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
  product_id VARCHAR(12) PRIMARY KEY,
  category_id VARCHAR(10) NOT NULL,
  product_name VARCHAR(200) NOT NULL,
  unit_price NUMERIC(14,2) NOT NULL CHECK (unit_price >= 0),
  cost_price NUMERIC(14,2) NOT NULL CHECK (cost_price >= 0),
  status VARCHAR(20) NOT NULL CHECK (status IN ('active','inactive','discontinued')),
  source_system VARCHAR(50) NOT NULL DEFAULT 'unknown',
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT products_category_id_fkey
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

-- Bang lookup trang thai don hang (order_status la PK, orders tham chieu vao day)
CREATE TABLE IF NOT EXISTS order_status (
  order_status VARCHAR(20) PRIMARY KEY
    CHECK (order_status IN ('pending','confirmed','shipped','completed','cancelled')),
  status_name VARCHAR(50) NOT NULL,
  status_order INTEGER NOT NULL CHECK (status_order > 0),
  is_final BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  order_id VARCHAR(12) PRIMARY KEY,
  customer_id VARCHAR(12) NOT NULL,
  order_date TIMESTAMPTZ NOT NULL,
  order_status VARCHAR(20) NOT NULL,
  shipping_city VARCHAR(100),
  channel VARCHAR(20) NOT NULL CHECK (channel IN ('web','mobile_app','social')),
  order_total NUMERIC(14,2) NOT NULL CHECK (order_total >= 0),
  source_system VARCHAR(50) NOT NULL DEFAULT 'unknown',
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT orders_customer_id_fkey
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
  CONSTRAINT orders_order_status_fkey
    FOREIGN KEY (order_status) REFERENCES order_status(order_status)
);

CREATE TABLE IF NOT EXISTS order_items (
  order_item_id VARCHAR(16) PRIMARY KEY,
  order_id VARCHAR(12) NOT NULL,
  product_id VARCHAR(12) NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price NUMERIC(14,2) NOT NULL CHECK (unit_price >= 0),
  discount_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  source_system VARCHAR(50) NOT NULL DEFAULT 'unknown',
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT order_items_check CHECK (discount_amount <= unit_price * quantity),
  CONSTRAINT order_items_order_id_fkey
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
  CONSTRAINT order_items_product_id_fkey
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS payments (
  payment_id VARCHAR(12) PRIMARY KEY,
  order_id VARCHAR(12) NOT NULL,
  payment_date TIMESTAMPTZ NOT NULL,
  payment_method VARCHAR(30) NOT NULL CHECK (payment_method IN ('cash','bank_transfer','card','e_wallet')),
  payment_status VARCHAR(20) NOT NULL CHECK (payment_status IN ('pending','success','failed','refunded')),
  amount NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
  source_system VARCHAR(50) NOT NULL DEFAULT 'unknown',
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT payments_order_id_fkey
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(order_status);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);

-- =====================================================================
-- Session 01 Bonus: Advanced Schema (CHECK constraints + DEFAULT audit)
-- Idempotent: DROP ... IF EXISTS truoc khi ADD de chay lai nhieu lan khong loi
-- =====================================================================

-- 1) CHECK constraints cho quy tac business
-- orders: ngay dat hang khong duoc o tuong lai
ALTER TABLE orders DROP CONSTRAINT IF EXISTS check_order_date;
ALTER TABLE orders ADD CONSTRAINT check_order_date
  CHECK (order_date IS NULL OR order_date <= NOW());

-- orders: updated_at khong duoc truoc created_at
ALTER TABLE orders DROP CONSTRAINT IF EXISTS check_orders_audit_ts;
ALTER TABLE orders ADD CONSTRAINT check_orders_audit_ts
  CHECK (updated_at >= created_at);

-- payments: ngay thanh toan khong o tuong lai, so tien > 0
ALTER TABLE payments DROP CONSTRAINT IF EXISTS check_payment_date;
ALTER TABLE payments ADD CONSTRAINT check_payment_date
  CHECK (payment_date <= NOW());

ALTER TABLE payments DROP CONSTRAINT IF EXISTS check_payment_amount_positive;
ALTER TABLE payments ADD CONSTRAINT check_payment_amount_positive
  CHECK (amount > 0);

-- order_items: so luong > 0 va gioi han hop ly
ALTER TABLE order_items DROP CONSTRAINT IF EXISTS check_quantity_range;
ALTER TABLE order_items ADD CONSTRAINT check_quantity_range
  CHECK (quantity > 0 AND quantity <= 1000);

-- products: gia ban khong thap hon gia von
ALTER TABLE products DROP CONSTRAINT IF EXISTS check_price_ge_cost;
ALTER TABLE products ADD CONSTRAINT check_price_ge_cost
  CHECK (unit_price >= cost_price);

-- customers: email dung dinh dang co ban
ALTER TABLE customers DROP CONSTRAINT IF EXISTS check_customer_email;
ALTER TABLE customers ADD CONSTRAINT check_customer_email
  CHECK (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$');

-- 2) DEFAULT cho audit fields tren cac bang chinh
ALTER TABLE categories   ALTER COLUMN created_at SET DEFAULT NOW(), ALTER COLUMN updated_at SET DEFAULT NOW();
ALTER TABLE customers    ALTER COLUMN created_at SET DEFAULT NOW(), ALTER COLUMN updated_at SET DEFAULT NOW();
ALTER TABLE products     ALTER COLUMN created_at SET DEFAULT NOW(), ALTER COLUMN updated_at SET DEFAULT NOW();
ALTER TABLE order_status ALTER COLUMN created_at SET DEFAULT NOW(), ALTER COLUMN updated_at SET DEFAULT NOW();
ALTER TABLE orders       ALTER COLUMN created_at SET DEFAULT NOW(), ALTER COLUMN updated_at SET DEFAULT NOW();
ALTER TABLE order_items  ALTER COLUMN created_at SET DEFAULT NOW(), ALTER COLUMN updated_at SET DEFAULT NOW();
ALTER TABLE payments     ALTER COLUMN created_at SET DEFAULT NOW(), ALTER COLUMN updated_at SET DEFAULT NOW();
