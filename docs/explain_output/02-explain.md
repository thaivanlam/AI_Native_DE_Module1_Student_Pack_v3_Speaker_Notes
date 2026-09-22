# Minh chứng 02 — Performance & Optimization (INDEX + EXPLAIN ANALYZE)

- **File script tái lập:** [sql/student/05_performance_index.sql](../../sql/student/05_performance_index.sql)
- **Output thô đầy đủ:** [docs/explain_output/02-explain-raw.txt](02-explain-raw.txt)
- **DDL index:** [sql/student/01_create_oltp.sql](../../sql/student/01_create_oltp.sql) (mục "Buoi 2.2 (Performance)")
- **Container ID:** `62030a96c66be7d49f3e90b5e41dbadc752aa3a7e598a5ea37fbac6467759317` (`ecommerce-postgres`)
- **Database:** `ecommerce`, schema `core`, user `de_user` — PostgreSQL 16.15 (Debian)
- **Thời điểm chạy:** 2026-09-20 18:28 +0700
- **Lệnh chạy:** `docker exec -i ecommerce-postgres psql -U de_user -d ecommerce -v ON_ERROR_STOP=1 < sql/student/05_performance_index.sql` → exit code 0

---

## 1. Vì sao cần INDEX cho cột hay dùng trong WHERE / JOIN

Không có index, PostgreSQL chỉ còn một cách duy nhất để biết dòng nào thoả điều kiện: **đọc toàn bộ heap của bảng rồi loại từng dòng một** (`Seq Scan` + `Filter`). Chi phí vì vậy tỉ lệ thuận với *kích thước bảng*, chứ không phải với *số dòng trả về* — trong ví dụ dưới đây query chỉ cần 626 dòng nhưng phải quét đủ 5000 dòng và vứt bỏ 4374 dòng (`Rows Removed by Filter: 4374`), tức ~87% công đọc là lãng phí.

Index B-tree trên đúng cột nằm trong `WHERE`/`JOIN` biến phép lọc đó thành **`Index Cond`** — điều kiện được đẩy xuống tận cây B-tree, engine nhảy thẳng tới khoảng khoá cần tìm và chỉ đọc đúng phần dữ liệu thoả mãn, nên chi phí tỉ lệ với *kết quả* thay vì với *bảng*. Với `JOIN` lý do còn mạnh hơn: có index trên cột khoá ngoại, planner mới được phép chọn Nested Loop + Index Scan (tra cứu O(log n) cho mỗi dòng bảng ngoài) thay vì buộc phải Hash Join và dựng hash table cho cả bảng.

Cụ thể với query bên dưới, thêm `INCLUDE (order_total)` đưa nốt cột cần `SUM()` vào leaf page, nên PostgreSQL đọc **hoàn toàn trong index, không đụng vào heap** (`Index Only Scan`, `Heap Fetches: 0`) — số block phải đọc giảm từ 78 xuống 6.

---

## 2. Query được chọn

Query lấy từ buổi này: **BQ1 — Total revenue theo tháng** trong [sql/student/02_exercises_basic.sql](../../sql/student/02_exercises_basic.sql).

Đây là ví dụ đại diện vì mệnh đề `WHERE` của nó gồm đúng hai dạng lọc phổ biến nhất trong báo cáo doanh thu:

| Cột | Dạng lọc | Vai trò |
|---|---|---|
| `order_status` | equality (`= 'completed'`) | chọn đơn hợp lệ theo quy ước KPI |
| `order_date` | range (`>= ... AND < ...`) | cắt cửa sổ 1 tháng |
| `order_total` | không lọc, chỉ `SUM()` | cột payload → ứng viên cho `INCLUDE` |

```sql
SELECT COUNT(*) AS completed_orders, COALESCE(SUM(order_total),0) AS total_revenue
FROM core.orders
WHERE order_status = 'completed'
  AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07'
  AND order_date <  TIMESTAMPTZ '2026-07-01 00:00:00+07';
```

> **Lưu ý về cửa sổ tháng:** BQ1 gốc hỏi tháng **2026-07**, nhưng dataset seed chỉ có dữ liệu từ `2026-01-01` đến `2026-06-29` nên cửa sổ đó trả về 0 row — không đo được gì. Bài đo này giữ nguyên hình dạng query và chỉ đổi sang tháng **2026-06** (626 đơn `completed`). Đây là khác biệt duy nhất so với BQ1.

**Index được tạo:**

```sql
CREATE INDEX IF NOT EXISTS idx_orders_status_date
  ON core.orders(order_status, order_date) INCLUDE (order_total);
```

Thứ tự cột theo quy tắc **equality trước, range sau**: `order_status` (dùng `=`) đặt trước, `order_date` (dùng range) đặt sau. Nếu đảo lại thành `(order_date, order_status)` thì sau khi B-tree đi vào khoảng range của `order_date`, cột `order_status` không còn nằm liên tục trong cây nữa nên chỉ dùng được làm `Filter`, không vào được `Index Cond`.

---

## 3. Phương pháp đo

Timing ở quy mô nhỏ rất nhiễu, nên mỗi trạng thái được đo theo cùng một quy trình:

1. `VACUUM ANALYZE core.orders` để stats và visibility map ổn định (visibility map là điều kiện bắt buộc để `Index Only Scan` đạt `Heap Fetches: 0`).
2. Chạy **3 lần warm-up** (bỏ kết quả) cho `shared_buffers` nóng — để so sánh CPU/IO logic chứ không so tốc độ đọc đĩa lần đầu.
3. Chạy **5 lần đo** lấy `Execution Time`, báo cáo **median** (median chịu nhiễu tốt hơn mean khi n nhỏ).
4. Chạy thêm 1 lần `EXPLAIN (ANALYZE, BUFFERS)` để lấy plan đại diện dán vào báo cáo.

Trạng thái A và B được dựng bằng `BEGIN; DROP INDEX ...; ... ROLLBACK;` — DDL trong PostgreSQL là transactional nên `ROLLBACK` trả index về nguyên vẹn, **không** phải build lại và **không** làm hỏng schema thật.

---

## 4. Output EXPLAIN — **TRƯỚC** khi tạo index

Trạng thái A: không có index nào trên `order_status` / `order_date`.

```sql
BEGIN;
DROP INDEX core.idx_orders_date;
DROP INDEX core.idx_orders_status;
DROP INDEX core.idx_orders_status_date;

EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS completed_orders, COALESCE(SUM(order_total),0) AS total_revenue
FROM core.orders
WHERE order_status = 'completed'
  AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07'
  AND order_date <  TIMESTAMPTZ '2026-07-01 00:00:00+07';
ROLLBACK;
```

```text
                                                        QUERY PLAN
---------------------------------------------------------------------------------------------------------------------------
 Aggregate  (cost=168.60..168.61 rows=1 width=40) (actual time=0.246..0.247 rows=1 loops=1)
   Buffers: shared hit=78
   ->  Seq Scan on orders  (cost=0.00..165.50 rows=619 width=6) (actual time=0.002..0.201 rows=626 loops=1)
         Filter: ((order_date >= '2026-05-31 17:00:00+00'::timestamp with time zone) AND (order_date < '2026-06-30 17:00:00+00'::timestamp with time zone) AND ((order_status)::text = 'completed'::text))
         Rows Removed by Filter: 4374
         Buffers: shared hit=78
 Planning Time: 0.028 ms
 Execution Time: 0.254 ms
(8 rows)
```

**Đọc plan:** cả 3 điều kiện nằm trong `Filter` — tức được áp *sau khi* đã đọc dòng lên khỏi đĩa. `Rows Removed by Filter: 4374` chính là công lãng phí. `Buffers: shared hit=78` = toàn bộ 78 block của heap `core.orders`.

---

## 5. Output EXPLAIN — **SAU** khi tạo index

Trạng thái C: có `idx_orders_status_date`.

```sql
CREATE INDEX IF NOT EXISTS idx_orders_status_date
  ON core.orders(order_status, order_date) INCLUDE (order_total);
VACUUM ANALYZE core.orders;

EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS completed_orders, COALESCE(SUM(order_total),0) AS total_revenue
FROM core.orders
WHERE order_status = 'completed'
  AND order_date >= TIMESTAMPTZ '2026-06-01 00:00:00+07'
  AND order_date <  TIMESTAMPTZ '2026-07-01 00:00:00+07';
```

```text
                                                        QUERY PLAN
---------------------------------------------------------------------------------------------------------------------------
 Aggregate  (cost=33.31..33.32 rows=1 width=40) (actual time=0.093..0.093 rows=1 loops=1)
   Buffers: shared hit=6
   ->  Index Only Scan using idx_orders_status_date on orders  (cost=0.28..30.21 rows=619 width=6) (actual time=0.010..0.056 rows=626 loops=1)
         Index Cond: ((order_status = 'completed'::text) AND (order_date >= '2026-05-31 17:00:00+00'::timestamp with time zone) AND (order_date < '2026-06-30 17:00:00+00'::timestamp with time zone))
         Heap Fetches: 0
         Buffers: shared hit=6
 Planning:
   Buffers: shared hit=3
 Planning Time: 0.069 ms
 Execution Time: 0.103 ms
(10 rows)
```

**Đọc plan:** `Filter` biến mất hoàn toàn — cả 3 điều kiện đã lên `Index Cond`, nên không còn dòng nào bị đọc thừa (`Rows Removed by Filter` không xuất hiện). `Heap Fetches: 0` xác nhận nhờ `INCLUDE (order_total)` mà query không cần chạm vào heap lần nào.

---

## 6. So sánh Execution Time

Bổ sung **trạng thái B** (chỉ có 2 index 1 cột `idx_orders_date` + `idx_orders_status`, đúng như schema trước buổi 2.2) để thấy rõ chênh lệch giữa "có index" và "có *đúng* index".

| | A — Không index | B — 2 index 1 cột | C — Composite covering |
|---|---|---|---|
| Kiểu scan | `Seq Scan` | `Bitmap Heap Scan` (qua `idx_orders_date`) | `Index Only Scan` |
| Điều kiện vào `Index Cond` | 0/3 | 1/3 (chỉ range `order_date`) | **3/3** |
| `Rows Removed by Filter` | 4374 | 169 | **0** |
| Buffers đọc | 78 | 83 | **6** |
| `Heap Fetches` | — (đọc cả heap) | 78 heap blocks | **0** |
| Estimated cost | 168.60 | 119.48 | **33.31** |
| **Execution Time (median 5 lần)** | **0.269 ms** | **0.199 ms** | **0.100 ms** |
| Execution Time (min / max) | 0.246 / 0.802 ms | 0.157 / 0.388 ms | 0.094 / 0.213 ms |

→ **A → C: nhanh hơn ~2.7×, số block phải đọc giảm 13×, cost ước lượng giảm 5.1×.**

Điểm đáng chú ý ở trạng thái B: index 1 cột `idx_orders_date` **có** được dùng, nhưng `order_status` vẫn rớt xuống `Filter`, và bitmap vẫn phải quay lại đọc đủ 78 heap block để lấy `order_total` — nên tổng buffers (83) còn *cao hơn* cả khi không có index (78). Nghĩa là: tạo index cho từng cột riêng lẻ không tương đương với một composite index đặt đúng thứ tự.

---

## 7. Kiểm chứng ở quy mô lớn (2.000.000 rows)

Ở 5000 dòng, `core.orders` chỉ nặng 624 kB nên nằm trọn trong `shared_buffers`; khác biệt tính bằng phần trăm mili-giây và dễ bị nhiễu đo lấn át (thấy rõ ở cột min/max bảng trên). Để kết luận không phụ thuộc nhiễu, PHẦN D của script dựng bảng `perf_lab.orders_big` **cùng shape, 2 triệu dòng (177 MB)**, chạy đúng query đó rồi `DROP SCHEMA perf_lab CASCADE` — schema `core` không bị ảnh hưởng.

| | Trước index | Sau index |
|---|---|---|
| Kiểu scan | `Parallel Seq Scan` (2 workers) | `Index Only Scan` |
| `Rows Removed by Filter` | 645.295 × 3 workers | 0 |
| Buffers | 22.606 (`hit=3470 read=19136`) | **427** |
| Estimated cost | 38.319 | **3.345** |
| **Execution Time (median 3 lần)** | **39.05 ms** | **9.58 ms** |

→ **Nhanh hơn 4.1×, đọc ít hơn 53× số block** — và đáng chú ý là bản có index đạt được điều đó **bằng 1 luồng đơn**, trong khi bản không index phải huy động 3 process song song mới về đích chậm hơn 4 lần.

---

## 8. Nhận xét & kết luận

1. **Index không làm query "chạy nhanh hơn", nó làm query "đọc ít đi".** Con số cốt lõi là `Buffers` và `Rows Removed by Filter`, còn `Execution Time` chỉ là hệ quả. Đây cũng là lý do ở dataset 5000 dòng nằm sẵn trong RAM, lợi ích đo bằng mili-giây trông khiêm tốn (0.27 → 0.10 ms) nhưng ở 2M dòng lại thành 39 → 9.6 ms: cùng một tỉ lệ đọc thừa, khác nhau ở chỗ dữ liệu có còn nằm vừa trong bộ nhớ hay không.

2. **Thứ tự cột trong composite index quyết định index có dùng được hết hay không.** `(order_status, order_date)` đưa được cả 3 điều kiện lên `Index Cond`; đảo lại sẽ chỉ dùng được cột đầu. Quy tắc: cột lọc `=` đặt trước, cột lọc range đặt sau.

3. **`INCLUDE` biến index thành covering index.** Đã đo riêng phần này: cùng composite `(order_status, order_date)` nhưng **bỏ `INCLUDE`**, cả 3 điều kiện vẫn lên `Index Cond`, nhưng vì `order_total` không có trong index nên plan tụt xuống `Bitmap Heap Scan` và phải quay lại heap đọc đủ `Heap Blocks: exact=78` → 83 buffers, median **0.165 ms**. Có `INCLUDE`: 6 buffers, `Heap Fetches: 0`, median **0.100 ms**. Cái giá phải trả là index nở từ **208 kB → 256 kB** (+23%) — đánh đổi dung lượng lấy số lần đọc.

4. **Index có chi phí, không phải càng nhiều càng tốt.** Mỗi index là một cấu trúc phải được cập nhật ở mọi `INSERT`/`UPDATE`/`DELETE`, tức làm chậm đường ghi và tốn thêm dung lượng. Với bảng `core.orders` hiện tại, tổng index (752 kB) đã lớn hơn cả heap (624 kB). Trong dự án thật nên theo dõi `pg_stat_user_indexes.idx_scan` để loại bỏ index không ai dùng.

5. **Tồn đọng đã ghi nhận:** `idx_orders_date` và `idx_orders_status` hiện gần như bị `idx_orders_status_date` thay thế cho nhóm query báo cáo doanh thu. Chưa xoá vì (a) hai index này vẫn phục vụ các query chỉ lọc theo ngày không kèm status (ví dụ Q5 — 5 orders mới nhất), và (b) cần theo dõi `idx_scan` qua vài buổi nữa mới đủ căn cứ. Sẽ đánh giá lại ở buổi tối ưu tiếp theo.

---

## 9. Cách tái lập

```bash
docker compose up -d postgres
docker exec -i ecommerce-postgres psql -U de_user -d ecommerce -v ON_ERROR_STOP=1 \
  < sql/student/05_performance_index.sql
```

Script tự dọn dẹp: trạng thái A/B chạy trong transaction rồi `ROLLBACK`, bảng 2M dòng bị `DROP` ở cuối. Kiểm tra cuối script xác nhận `core.orders` vẫn còn đủ 5 index:

```text
       indexname        | index_size
------------------------+------------
 idx_orders_customer    | 88 kB
 idx_orders_date        | 160 kB
 idx_orders_status      | 72 kB
 idx_orders_status_date | 256 kB
 orders_pkey            | 176 kB
(5 rows)
```
