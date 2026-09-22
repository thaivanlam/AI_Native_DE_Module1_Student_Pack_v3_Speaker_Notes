-- ============================================================
-- 2.2 Performance & Optimization — EXPLAIN ANALYZE truoc/sau khi tao INDEX
-- Bao cao: docs/explain_output/02-explain.md
--
-- Cach chay:
--   docker exec -i ecommerce-postgres psql -U de_user -d ecommerce -v ON_ERROR_STOP=1 < sql/student/05_performance_index.sql
--
-- Script chay duoc nhieu lan (idempotent):
--   - PHAN A/B do trong BEGIN ... ROLLBACK nen index bi DROP duoc tra lai nguyen ven
--     (DDL trong PostgreSQL la transactional -> ROLLBACK khong phai rebuild index).
--   - PHAN D tao rieng schema perf_lab roi DROP o cuoi, khong dung den schema core.
-- ============================================================

-- Dat lai stats ve trang thai on dinh truoc khi do
VACUUM ANALYZE core.orders;

-- Query do hieu nang: BQ1 (total revenue 1 thang) trong 02_exercises_basic.sql.
-- Khac biet duy nhat: doi cua so sang thang 2026-06 vi dataset seed chi co du lieu
-- 2026-01-01 .. 2026-06-29, cua so 2026-07 cua BQ1 tra ve 0 row nen khong do duoc gi.
--   WHERE order_status = 'completed'   -> loc dang equality
--     AND order_date  >= ... AND < ... -> loc dang range
--   SELECT COUNT(*), SUM(order_total)  -> chi can doc them cot order_total

-- ============================================================
-- PHAN A — TRUOC: khong co index nao tren order_status / order_date
-- ============================================================
BEGIN;
DROP INDEX core.idx_orders_date;
DROP INDEX core.idx_orders_status;
DROP INDEX core.idx_orders_status_date;

-- 3 lan warm-up cho shared_buffers nong, ket qua bo di
\o /dev/null
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM core.orders WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2026-07-01 00:00:00+07';
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM core.orders WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2026-07-01 00:00:00+07';
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM core.orders WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2026-07-01 00:00:00+07';
\o

\echo '######## TRANG THAI A - KHONG CO INDEX ########'
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS completed_orders, COALESCE(SUM(order_total),0) AS total_revenue
FROM core.orders
WHERE order_status = 'completed'
  AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07'
  AND order_date <  TIMESTAMPTZ '2026-07-01 00:00:00+07';
ROLLBACK;

-- ============================================================
-- PHAN B — GIUA: chi co 2 index 1 cot (trang thai schema truoc buoi 2.2)
-- ============================================================
BEGIN;
DROP INDEX core.idx_orders_status_date;

\o /dev/null
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM core.orders WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2026-07-01 00:00:00+07';
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM core.orders WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2026-07-01 00:00:00+07';
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM core.orders WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2026-07-01 00:00:00+07';
\o

\echo '######## TRANG THAI B - CHI INDEX 1 COT ########'
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS completed_orders, COALESCE(SUM(order_total),0) AS total_revenue
FROM core.orders
WHERE order_status = 'completed'
  AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07'
  AND order_date <  TIMESTAMPTZ '2026-07-01 00:00:00+07';
ROLLBACK;

-- ============================================================
-- PHAN C — SAU: composite covering index (da co san trong 01_create_oltp.sql)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_orders_status_date
  ON core.orders(order_status, order_date) INCLUDE (order_total);
VACUUM ANALYZE core.orders;   -- set visibility map -> Index Only Scan moi dat Heap Fetches: 0

\o /dev/null
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM core.orders WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2026-07-01 00:00:00+07';
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM core.orders WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2026-07-01 00:00:00+07';
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM core.orders WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2026-07-01 00:00:00+07';
\o

\echo '######## TRANG THAI C - COMPOSITE COVERING INDEX ########'
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS completed_orders, COALESCE(SUM(order_total),0) AS total_revenue
FROM core.orders
WHERE order_status = 'completed'
  AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07'
  AND order_date <  TIMESTAMPTZ '2026-07-01 00:00:00+07';

-- ============================================================
-- PHAN D — Kiem chung o quy mo lon (2.000.000 rows)
-- Ly do: core.orders chi 5000 rows / 624 kB, nam gon trong shared_buffers nen chenh
-- lech Execution Time (0.27 ms vs 0.10 ms) nho, de bi nhieu do lan at.
-- Bang perf_lab.orders_big mo phong cung shape de thay khac biet ro rang.
-- Bang nay bi DROP o cuoi script, schema core khong bi anh huong.
-- ============================================================
CREATE SCHEMA IF NOT EXISTS perf_lab;
DROP TABLE IF EXISTS perf_lab.orders_big;
CREATE TABLE perf_lab.orders_big AS
SELECT 'ORD' || LPAD(g::text, 10, '0')                  AS order_id,
       'CUS' || LPAD(((g % 100000) + 1)::text, 8, '0')  AS customer_id,
       TIMESTAMPTZ '2024-01-01 00:00:00+07'
         + ((g % 730)   * INTERVAL '1 day')
         + ((g % 86400) * INTERVAL '1 second')          AS order_date,
       CASE WHEN g % 100 < 78 THEN 'completed'
            WHEN g % 100 < 87 THEN 'shipped'
            WHEN g % 100 < 92 THEN 'confirmed'
            WHEN g % 100 < 97 THEN 'cancelled'
            ELSE 'pending' END                          AS order_status,
       ROUND((50000 + (g % 4500000))::numeric / 100, 2) AS order_total
FROM generate_series(1, 2000000) g;
VACUUM ANALYZE perf_lab.orders_big;

\o /dev/null
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM perf_lab.orders_big WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2024-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2024-07-01 00:00:00+07';
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM perf_lab.orders_big WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2024-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2024-07-01 00:00:00+07';
\o

\echo '######## 2M ROWS - TRUOC INDEX ########'
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS completed_orders, COALESCE(SUM(order_total),0) AS total_revenue
FROM perf_lab.orders_big
WHERE order_status = 'completed'
  AND order_date >= TIMESTAMPTZ '2024-06-01 00:00:00+07'
  AND order_date <  TIMESTAMPTZ '2024-07-01 00:00:00+07';

CREATE INDEX idx_big_status_date
  ON perf_lab.orders_big(order_status, order_date) INCLUDE (order_total);
VACUUM ANALYZE perf_lab.orders_big;

\o /dev/null
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM perf_lab.orders_big WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2024-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2024-07-01 00:00:00+07';
EXPLAIN (ANALYZE) SELECT COUNT(*), COALESCE(SUM(order_total),0) FROM perf_lab.orders_big WHERE order_status = 'completed' AND order_date >= TIMESTAMPTZ '2024-06-01 00:00:00+07' AND order_date < TIMESTAMPTZ '2024-07-01 00:00:00+07';
\o

\echo '######## 2M ROWS - SAU INDEX ########'
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS completed_orders, COALESCE(SUM(order_total),0) AS total_revenue
FROM perf_lab.orders_big
WHERE order_status = 'completed'
  AND order_date >= TIMESTAMPTZ '2024-06-01 00:00:00+07'
  AND order_date <  TIMESTAMPTZ '2024-07-01 00:00:00+07';

-- Don dep bang thu nghiem
DROP SCHEMA perf_lab CASCADE;

-- Kiem tra lai: core.orders phai con du 5 index (4 index phu + PK)
SELECT indexname, pg_size_pretty(pg_relation_size(('core.'||indexname)::regclass)) AS index_size
FROM pg_indexes
WHERE schemaname = 'core' AND tablename = 'orders'
ORDER BY indexname;
