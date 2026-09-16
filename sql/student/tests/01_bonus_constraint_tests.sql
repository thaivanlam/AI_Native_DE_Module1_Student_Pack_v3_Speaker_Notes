-- Session 01 Bonus: test cac CHECK/DEFAULT constraint
-- Chay: docker exec -i ecommerce-postgres psql -U de_user -d ecommerce < sql/student/tests/01_bonus_constraint_tests.sql
-- Tat ca chay trong 1 transaction va ROLLBACK cuoi cung -> khong de lai du lieu.
\set ON_ERROR_ROLLBACK on
\set ECHO queries
SET search_path TO core, public;
BEGIN;

-- Du lieu hop le (khong truyen created_at/updated_at -> dung DEFAULT NOW())
INSERT INTO categories (category_id, category_name) VALUES ('CAT_T1', 'Test Category');
INSERT INTO customers (customer_id, full_name, email, customer_segment, status)
  VALUES ('CUS_T1', 'Test User', 'test@example.com', 'retail', 'active');
INSERT INTO products (product_id, category_id, product_name, unit_price, cost_price, status)
  VALUES ('PRD_T1', 'CAT_T1', 'Test Product', 100, 60, 'active');
INSERT INTO order_status (order_status, status_name, status_order)
  VALUES ('pending', 'Pending', 1) ON CONFLICT DO NOTHING;
INSERT INTO orders (order_id, customer_id, order_date, order_status, channel, order_total)
  VALUES ('ORD_T1', 'CUS_T1', NOW() - INTERVAL '1 day', 'pending', 'web', 100);
SELECT order_id, created_at, updated_at FROM orders WHERE order_id = 'ORD_T1';

-- VI PHAM 1: order_date o tuong lai -> check_order_date
INSERT INTO orders (order_id, customer_id, order_date, order_status, channel, order_total)
  VALUES ('ORD_T2', 'CUS_T1', NOW() + INTERVAL '10 days', 'pending', 'web', 100);

-- VI PHAM 2: order_total am -> orders_order_total_check
INSERT INTO orders (order_id, customer_id, order_date, order_status, channel, order_total)
  VALUES ('ORD_T3', 'CUS_T1', NOW(), 'pending', 'web', -50);

-- VI PHAM 3: updated_at truoc created_at -> check_orders_audit_ts
INSERT INTO orders (order_id, customer_id, order_date, order_status, channel, order_total, created_at, updated_at)
  VALUES ('ORD_T4', 'CUS_T1', NOW(), 'pending', 'web', 10, NOW(), NOW() - INTERVAL '1 hour');

-- VI PHAM 4: payment amount am -> payments_amount_check / check_payment_amount_positive
INSERT INTO payments (payment_id, order_id, payment_date, payment_method, payment_status, amount)
  VALUES ('PAY_T1', 'ORD_T1', NOW(), 'card', 'success', -100);

-- VI PHAM 5: payment_date o tuong lai -> check_payment_date
INSERT INTO payments (payment_id, order_id, payment_date, payment_method, payment_status, amount)
  VALUES ('PAY_T2', 'ORD_T1', NOW() + INTERVAL '1 day', 'card', 'success', 100);

-- VI PHAM 6: quantity = 0 -> order_items_quantity_check
INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price)
  VALUES ('OIT_T1', 'ORD_T1', 'PRD_T1', 0, 100);

-- VI PHAM 7: quantity qua lon -> check_quantity_range
INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price)
  VALUES ('OIT_T2', 'ORD_T1', 'PRD_T1', 5000, 100);

-- VI PHAM 8: gia ban < gia von -> check_price_ge_cost
INSERT INTO products (product_id, category_id, product_name, unit_price, cost_price, status)
  VALUES ('PRD_T2', 'CAT_T1', 'Loss Product', 50, 80, 'active');

-- VI PHAM 9: email sai dinh dang -> check_customer_email
INSERT INTO customers (customer_id, full_name, email, customer_segment, status)
  VALUES ('CUS_T2', 'Bad Email', 'not-an-email', 'retail', 'active');

-- Liet ke cac constraint bonus da tao
SELECT conrelid::regclass AS table_name, conname
FROM pg_constraint
WHERE connamespace = 'core'::regnamespace AND contype = 'c' AND conname LIKE 'check_%'
ORDER BY 1, 2;

ROLLBACK;
