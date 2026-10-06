-- 04_bonus_scd.sql
-- Buoi 4 - 2.1 Advanced Mart Design, phuong an (a): SCD Type 2 cho mart.dim_product.
-- Chay SAU sql/student/04_data_mart.sql (can mart.dim_product va mart.fact_sales da co du lieu).
--
-- =====================================================================
-- VAN DE
-- =====================================================================
--   dim_product ban dau la SCD Type 1: moi product_id 1 dong, doi gia thi ghi de
--   -> mat lich su. Bao cao "ban hang theo muc gia niem yet" hay "bien loi nhuan
--   theo gia von tai thoi diem ban" se sai cho cac don cu.
--
-- SCD TYPE 2: moi lan thuoc tinh theo doi thay doi thi DONG phien ban cu va MO
--   phien ban moi (surrogate key moi), khong ghi de.
--   - valid_from / valid_to : khoang ngay hieu luc cua phien ban, tinh ca 2 dau mut
--                             (phien ban dang hieu luc co valid_to = 9999-12-31).
--   - is_current            : TRUE cho dung 1 phien ban moi nhat cua moi product_id.
--   - Thuoc tinh theo doi (Type 2): list_price, cost_price, category_id.
--   - Fact giu nguyen product_key cu -> don cu van gan voi gia cu; don moi lookup
--     phien ban is_current (hoac theo ngay: order_date BETWEEN valid_from AND valid_to).
--
-- Tuong thich voi 04_data_mart.sql: script load chinh TRUNCATE + nap lai nen moi
--   product_id chi co 1 dong, 3 cot moi nhan gia tri DEFAULT (1 phien ban dang hieu
--   luc tu 1900-01-01) -> chay lai file chinh van dung.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) DDL: them 3 cot SCD2 + doi rang buoc khoa (idempotent, chay lai khong loi)
-- ---------------------------------------------------------------------
ALTER TABLE mart.dim_product
  ADD COLUMN IF NOT EXISTS valid_from DATE NOT NULL DEFAULT DATE '1900-01-01',
  ADD COLUMN IF NOT EXISTS valid_to DATE NOT NULL DEFAULT DATE '9999-12-31',
  ADD COLUMN IF NOT EXISTS is_current BOOLEAN NOT NULL DEFAULT TRUE;

-- product_id khong con UNIQUE (1 san pham co nhieu phien ban) -> bo rang buoc cu,
-- thay bang 2 rang buoc dung nghia SCD2:
--   - moi product_id chi co toi da 1 dong is_current (partial unique index);
--   - khong co 2 phien ban cung ngay bat dau.
ALTER TABLE mart.dim_product DROP CONSTRAINT IF EXISTS dim_product_product_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_product_current
  ON mart.dim_product(product_id) WHERE is_current;

ALTER TABLE mart.dim_product DROP CONSTRAINT IF EXISTS dim_product_version_key;
ALTER TABLE mart.dim_product ADD CONSTRAINT dim_product_version_key
  UNIQUE (product_id, valid_from);

ALTER TABLE mart.dim_product DROP CONSTRAINT IF EXISTS dim_product_valid_range_check;
ALTER TABLE mart.dim_product ADD CONSTRAINT dim_product_valid_range_check
  CHECK (valid_to >= valid_from);

-- ---------------------------------------------------------------------
-- 2) DEMO: 1 san pham doi gia (PRD000297, tang gia niem yet 10%)
-- ---------------------------------------------------------------------
-- Toan bo demo nam trong 1 transaction va ket thuc bang ROLLBACK: viec doi gia
-- tren core.products chi la GIA LAP de chung minh SCD2 hoat dong, khong duoc de
-- lai trong OLTP / mart (cac so lieu doi soat 1.3 va KPI 1.4 giu nguyen).
BEGIN;

-- D1 - TRUOC khi doi gia: san pham co 1 phien ban dang hieu luc.
SELECT product_key, product_id, list_price, cost_price, valid_from, valid_to, is_current
FROM mart.dim_product
WHERE product_id = 'PRD000297'
ORDER BY valid_from;

-- Gia lap thay doi o nguon: OLTP tang gia san pham 10%.
UPDATE core.products
SET unit_price = ROUND(unit_price * 1.10, 0),
    updated_at = NOW()
WHERE product_id = 'PRD000297';

-- SCD2 buoc 1 - DONG phien ban hien tai cua nhung san pham co thuoc tinh theo doi
-- khac voi nguon: valid_to = ngay truoc ngay thay doi, is_current = FALSE.
UPDATE mart.dim_product d
SET valid_to = (p.updated_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - 1,
    is_current = FALSE
FROM core.products p
WHERE p.product_id = d.product_id
  AND d.is_current
  AND (d.list_price <> p.unit_price
       OR d.cost_price <> p.cost_price
       OR d.category_id <> p.category_id);

-- SCD2 buoc 2 - MO phien ban moi cho moi san pham chua co dong is_current
-- (san pham vua bi dong o buoc 1, hoac san pham moi hoan toan).
-- valid_from = ngay thay doi neu da co phien ban cu, nguoc lai = 1900-01-01.
INSERT INTO mart.dim_product
  (product_id, product_name, category_id, category, parent_category,
   list_price, cost_price, status, valid_from, valid_to, is_current)
SELECT p.product_id, p.product_name, p.category_id, c.category_name,
       COALESCE(pc.category_name, c.category_name),
       p.unit_price, p.cost_price, p.status,
       CASE WHEN EXISTS (SELECT 1 FROM mart.dim_product o WHERE o.product_id = p.product_id)
            THEN (p.updated_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
            ELSE DATE '1900-01-01'
       END,
       DATE '9999-12-31',
       TRUE
FROM core.products p
JOIN core.categories c ON c.category_id = p.category_id
LEFT JOIN core.categories pc ON pc.category_id = c.parent_category_id
WHERE NOT EXISTS (SELECT 1 FROM mart.dim_product d
                  WHERE d.product_id = p.product_id AND d.is_current);

-- D2 - SAU khi doi gia: 2 phien ban, phien ban cu da dong, phien ban moi dang hieu luc.
SELECT product_key, product_id, list_price, cost_price, valid_from, valid_to, is_current
FROM mart.dim_product
WHERE product_id = 'PRD000297'
ORDER BY valid_from;

-- D3 - Lich su duoc giu: cac dong fact cu van tro ve phien ban cu (gia cu);
-- phien ban moi chua co dong ban nao.
SELECT p.product_key, p.list_price, p.is_current,
       COUNT(f.sales_key)          AS fact_rows,
       COALESCE(SUM(f.quantity), 0) AS units_sold,
       COALESCE(SUM(f.revenue), 0)  AS revenue
FROM mart.dim_product p
LEFT JOIN mart.fact_sales f ON f.product_key = p.product_key
WHERE p.product_id = 'PRD000297'
GROUP BY p.product_key, p.list_price, p.is_current
ORDER BY p.product_key;

-- D4 - Tra cuu theo thoi diem (point-in-time): cung 1 product_id, moi ngay ra dung
-- phien ban co hieu luc ngay do. Day la dieu kien JOIN khi load fact voi SCD2.
SELECT a.as_of, p.product_key, p.list_price, p.valid_from, p.valid_to
FROM (VALUES (DATE '2026-06-29'),
             ((NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)) AS a(as_of)
JOIN mart.dim_product p
  ON p.product_id = 'PRD000297'
 AND a.as_of BETWEEN p.valid_from AND p.valid_to
ORDER BY a.as_of;

-- D5 - Toan ven: tong so dong tang dung 1, van 500 product_id, khong product_id
-- nao co so dong is_current khac 1.
SELECT COUNT(*)                            AS dim_rows,
       COUNT(DISTINCT product_id)          AS products,
       COUNT(*) FILTER (WHERE is_current)  AS current_rows,
       (SELECT COUNT(*) FROM (SELECT product_id FROM mart.dim_product
                              GROUP BY product_id
                              HAVING COUNT(*) FILTER (WHERE is_current) <> 1) x)
                                           AS products_without_exactly_1_current
FROM mart.dim_product;

-- D6 - Idempotent: chay lai buoc 1 khi nguon khong doi them -> UPDATE 0 (khong
-- sinh phien ban thua).
UPDATE mart.dim_product d
SET valid_to = (p.updated_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - 1,
    is_current = FALSE
FROM core.products p
WHERE p.product_id = d.product_id
  AND d.is_current
  AND (d.list_price <> p.unit_price
       OR d.cost_price <> p.cost_price
       OR d.category_id <> p.category_id);

ROLLBACK;

-- D7 - Sau ROLLBACK: OLTP va mart tro lai nhu truoc demo (1 phien ban, gia cu).
SELECT d.product_key, d.product_id, d.list_price, p.unit_price AS oltp_unit_price,
       d.valid_from, d.valid_to, d.is_current
FROM mart.dim_product d
JOIN core.products p ON p.product_id = d.product_id
WHERE d.product_id = 'PRD000297';
