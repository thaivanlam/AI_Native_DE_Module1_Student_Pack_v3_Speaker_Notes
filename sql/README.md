# SQL – Hướng dẫn chạy scripts

Thư mục này chứa các script SQL của lớp OLTP (schema `core`) cho database `ecommerce` (PostgreSQL 16 chạy trong Docker).

```
sql/
├── README.md
└── student/
    ├── 01_create_oltp.sql          # DDL: tạo schema core, 7 bảng, FK, index, CHECK/DEFAULT
    ├── 02_exercises_basic.sql      # Bài tập truy vấn cơ bản (session sau)
    ├── 03_exercises_advanced.sql   # Bài tập truy vấn nâng cao (session sau)
    ├── 04_data_mart.sql            # Data mart (session sau)
    └── tests/
        └── 01_bonus_constraint_tests.sql   # Test CHECK/DEFAULT (chạy trong transaction, ROLLBACK)
```

## Thứ tự chạy

| Bước | Việc làm | Lệnh / Script |
|---|---|---|
| 0 | Chuẩn bị `.env` | `cp .env.example .env` |
| 1 | Tạo DB (khởi động PostgreSQL) | `docker compose up -d postgres` |
| 2 | Tạo schema + bảng | `sql/student/01_create_oltp.sql` |
| 3 | Verify | các câu query ở mục 3 |
| 4 | (Tuỳ chọn) Nạp seed data | `scripts/bootstrap_core.sh` |
| 5 | (Bonus) Test constraint | `sql/student/tests/01_bonus_constraint_tests.sql` |

> Các lệnh dưới đây chạy từ **thư mục gốc của repo**, dùng thông số mặc định trong `.env.example`:
> DB `ecommerce`, user `de_user`, password `de_password`, container `ecommerce-postgres`, port `5432`.

### 1. Tạo database

Database `ecommerce` được container tạo tự động từ biến `POSTGRES_DB` trong `docker-compose.yml`.

```bash
cp .env.example .env            # chỉ cần làm lần đầu
docker compose up -d postgres
docker compose ps               # chờ trạng thái "healthy"
```

Kiểm tra kết nối:

```bash
docker exec -it ecommerce-postgres psql -U de_user -d ecommerce -c "SELECT current_database(), version();"
```

### 2. Chạy `01_create_oltp.sql`

```bash
docker exec -i ecommerce-postgres psql -U de_user -d ecommerce -v ON_ERROR_STOP=1 < sql/student/01_create_oltp.sql
```

- `-v ON_ERROR_STOP=1`: dừng ngay ở lỗi đầu tiên thay vì chạy tiếp.
- Script **idempotent** (`IF NOT EXISTS`, `DROP CONSTRAINT IF EXISTS`) → chạy lại nhiều lần không lỗi.
- Các bảng được tạo theo thứ tự **cha trước, con sau**:
  `categories → customers → products → order_status → orders → order_items → payments`.

Muốn làm lại từ đầu (xoá schema cũ):

```bash
docker exec -i ecommerce-postgres psql -U de_user -d ecommerce -c "DROP SCHEMA IF EXISTS core CASCADE;"
```

> PowerShell (Windows) không hỗ trợ `<` để redirect. Dùng:
> `Get-Content sql/student/01_create_oltp.sql -Raw | docker exec -i ecommerce-postgres psql -U de_user -d ecommerce -v ON_ERROR_STOP=1`

### 3. Verify

Mở psql: `docker exec -it ecommerce-postgres psql -U de_user -d ecommerce`, rồi chạy:

```sql
-- 3.1 Có đủ 7 bảng trong schema core
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'core'
ORDER BY table_name;
-- Kỳ vọng: categories, customers, order_items, order_status, orders, payments, products

-- 3.2 Có đủ 7 khoá ngoại, đúng bảng cha - con
SELECT conrelid::regclass  AS child_table,
       confrelid::regclass AS parent_table,
       conname,
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE connamespace = 'core'::regnamespace AND contype = 'f'
ORDER BY 1, 2;

-- 3.3 Index trên các cột FK
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'core' AND indexname LIKE 'idx_%'
ORDER BY 1, 2;

-- 3.4 CHECK constraint (phần bonus)
SELECT conrelid::regclass AS table_name, conname
FROM pg_constraint
WHERE connamespace = 'core'::regnamespace AND contype = 'c'
ORDER BY 1, 2;
```

Hoặc dùng lệnh meta của psql: `\dt core.*`, `\d core.orders`.

Kết quả verify nên được lưu làm minh chứng vào `docs/evidence/` (ví dụ `01-verify-db.txt`).

### 4. (Tuỳ chọn) Nạp seed data

```bash
bash scripts/bootstrap_core.sh
```

Script này **xoá schema `core`/`mart`**, chạy lại `01_create_oltp.sql` và nạp CSV trong `data/seed/` theo thứ tự cha → con. Nếu bước này lỗi, sửa `01_create_oltp.sql` trước.

### 5. (Bonus) Test constraint

```bash
docker exec -i ecommerce-postgres psql -U de_user -d ecommerce < sql/student/tests/01_bonus_constraint_tests.sql
```

Các câu INSERT vi phạm phải báo lỗi `violates check constraint ...`. Toàn bộ chạy trong 1 transaction và `ROLLBACK` ở cuối nên không để lại dữ liệu.

## Quan hệ giữa các bảng

Ký hiệu `A 1 ──< n B`: A là bảng cha, B là bảng con (B chứa FK trỏ về A).

```
categories   1 ──< n categories    (tự tham chiếu: danh mục cha - con)
categories   1 ──< n products
products     1 ──< n order_items
customers    1 ──< n orders
order_status 1 ──< n orders
orders       1 ──< n order_items   (ON DELETE CASCADE)
orders       1 ──< n payments
```

`order_items` là bảng cầu nối cho quan hệ n-n giữa `orders` và `products`.

| Bảng con | Cột FK | Bảng cha | Ý nghĩa |
|---|---|---|---|
| `categories` | `parent_category_id` | `categories` | Danh mục đa cấp; `NULL` = danh mục gốc |
| `products` | `category_id` | `categories` | Mỗi sản phẩm thuộc đúng 1 danh mục |
| `orders` | `customer_id` | `customers` | Mỗi đơn thuộc 1 khách hàng có thật |
| `orders` | `order_status` | `order_status` | Trạng thái đơn chỉ lấy từ bảng lookup |
| `order_items` | `order_id` | `orders` | Dòng hàng của đơn; xoá đơn → xoá dòng hàng (`CASCADE`) |
| `order_items` | `product_id` | `products` | Dòng hàng trỏ tới sản phẩm có thật |
| `payments` | `order_id` | `orders` | Giao dịch thanh toán của đơn; không xoá được đơn đã có thanh toán |

Chi tiết từng FK được ghi chú bằng comment ngay trong [student/01_create_oltp.sql](student/01_create_oltp.sql). Sơ đồ DBML gốc: [../database/ecommerce_oltp.dbml](../database/ecommerce_oltp.dbml).
