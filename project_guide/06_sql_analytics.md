# 6. SQL Analytics (Buổi 2–3)

← [5. Database OLTP](05_database_oltp.md) · Tiếp: [7. Data Mart](07_data_mart.md) →

Toàn bộ truy vấn chạy trên schema `core` sau khi nạp seed (5.000 đơn, 01/01 – 29/06/2026).

## 6.1 Quy ước tính KPI (áp dụng cho mọi query)

| Quy ước | Chi tiết |
|---|---|
| **Revenue** | `SUM(orders.order_total)` của đơn `completed` (order_total đã trừ discount – đối soát khớp ở Q15). Một số bài tập Buổi 2 (Q6–Q10) dùng "khác `cancelled`" theo đề. |
| **Revenue theo dòng hàng** | `quantity × unit_price − discount_amount` (dùng khi cần tách theo category/product) |
| **Tháng** | `DATE_TRUNC('month', order_date AT TIME ZONE 'Asia/Ho_Chi_Minh')` – vì `order_date` là `TIMESTAMPTZ` |
| **Đơn vị tiền** | VND |

## 6.2 Bản đồ file

| File | Nội dung | Evidence |
|---|---|---|
| [02_exercises_basic.sql](../sql/student/02_exercises_basic.sql) | Q1–Q5 cơ bản, Q6–Q10 aggregate, Q11–Q15 JOIN, BQ1–BQ5 business | `02-basic-results.md`, `02-agg-results.txt`, `02-join-q5.txt`, `02-business-results.txt`, [answers_02.md](../docs/answers_02.md) |
| [03_exercises_advanced.sql](../sql/student/03_exercises_advanced.sql) | Bonus 2.1: doanh thu luỹ kế, tỷ trọng category, khách churn 30 ngày | `02-bonus.txt` |
| [03_cte_window_cohort.sql](../sql/student/03_cte_window_cohort.sql) | CTE1–5, W1–5, RFM, Cohort, RFM score, Time series | `03-cte-results.txt`, `03-window-results.txt`, `03-rfm-segments.csv`, `03-cohort.png`, `03-timeseries.txt` |
| [05_performance_index.sql](../sql/student/05_performance_index.sql) | EXPLAIN ANALYZE trước/sau index | [explain_output/02-explain.md](../docs/explain_output/02-explain.md) |

## 6.3 Buổi 2 – SQL cơ bản & câu hỏi kinh doanh

### Nhóm truy vấn
| Nhóm | Câu | Kỹ thuật |
|---|---|---|
| 1.1 Basic | Q1–Q5 | `WHERE`, `LEFT JOIN … IS NULL` (khách chưa mua), `ORDER BY … LIMIT`, `COUNT(DISTINCT)` |
| 1.2 Aggregate | Q6–Q10 | `DATE_TRUNC`, `GROUP BY`, `HAVING`, doanh thu theo category qua 4 bảng |
| 1.3 JOIN | Q11–Q15 | JOIN nhiều bảng; Q13 tìm đơn có payment mà không có item (và ngược lại); Q14 sản phẩm chưa từng bán; **Q15 đối soát** `order_total` với tổng item |
| 1.4 Business | BQ1–BQ5 | KPI theo quy ước completed |

### Kết quả BQ1–BQ5 ([answers_02.md](../docs/answers_02.md))
| # | Câu hỏi | Đáp án |
|---|---|---|
| 1 | Total revenue tháng 7/2026 | **0 VND** – CORE chưa có dữ liệu tháng 7 (nằm trong batch incremental chưa nạp: 361 đơn completed, 4,37 tỷ) |
| 2 | Khách chi tiêu cao nhất | **CUS000736 – Gordon Rogers – 173.654.000 VND** (10 đơn) |
| 3 | Category nhiều đơn nhất | **CAT012 – Skincare – 824 đơn** |
| 4 | AOV | **12.391.222,68 VND** |
| 5 | Số khách có > 3 đơn completed | **530** |

### Bonus 2.1 – Window functions ([03_exercises_advanced.sql](../sql/student/03_exercises_advanced.sql))
- **B1** Doanh thu luỹ kế theo tháng: `SUM(...) OVER (ORDER BY month)` + % luỹ kế.
- **B2** Tỷ trọng doanh thu category: `SUM(...) OVER ()` làm mẫu số, kèm `RANK()` và % luỹ kế (Pareto).
- **B3** Khách "churn": không có đơn trong 30 ngày tính từ `MAX(order_date)` của dataset (không dùng `NOW()` vì dữ liệu là snapshot lịch sử).

## 6.4 Buổi 3 – CTE, Window, Customer Analytics

### 1.1 CTE refactoring
| Query | Mục đích |
|---|---|
| CTE1 | Top 10 khách theo tổng chi tiêu |
| CTE2 | Phân tầng Low / Medium / High (ngưỡng USD quy đổi 1 USD = 25.000 VND, đặt trong CTE `params`) |
| CTE3 | CTE lồng nhau: số đơn / khách → MIN/MAX/AVG phân bố |
| CTE4 | AOV từng khách (`NULLIF` chống chia 0) |
| CTE5 | Retention đơn giản: % khách quay lại ở bất kỳ tháng nào sau tháng đầu; kèm `months_observed` để không hiểu nhầm cohort mới |

### 1.2 Window functions
| Query | Hàm | Bài học |
|---|---|---|
| W1 | `ROW_NUMBER()` | Xếp hạng khách, luôn duy nhất |
| W2 | `RANK()` vs `DENSE_RANK()` | Xếp theo số đơn (chỉ 12 giá trị) để thấy RANK "nhảy số" còn DENSE_RANK thì không |
| W3 | `ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date)` | Số thứ tự đơn của từng khách – nền cho cohort |
| W4 | `LAG()` / `LEAD()` | So sánh đơn trước/sau cùng khách |
| W5 | `SUM() OVER (ORDER BY … ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)` | Running total; giải thích khác biệt frame `ROWS` và `RANGE` |

### 1.3 RFM (3 chỉ số trong 1 bảng)
Một `GROUP BY customer_id` duy nhất trên đơn completed:
- **Recency** = số ngày từ đơn cuối tới `NOW()`
- **Frequency** = số đơn
- **Monetary** = tổng tiền

Kết quả: [docs/customer_rfm.csv](../docs/customer_rfm.csv).

### 1.4 Cohort retention
Ma trận cohort (tháng mua đầu) × M0…M5, giá trị = % khách có mua ở đúng tháng thứ N.

| Cohort | Size | M0 | M1 | M2 | M3 | M4 | M5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-01 | 479 | 100 | 45.93 | 50.10 | 45.09 | 47.39 | 47.60 |
| 2026-02 | 219 | 100 | 45.21 | 47.95 | 41.10 | 50.68 | |
| 2026-03 | 158 | 100 | 52.53 | 51.90 | 44.30 | | |
| 2026-04 | 60 | 100 | 46.67 | 43.33 | | | |
| 2026-05 | 42 | 100 | 38.10 | | | | |
| 2026-06 | 15 | 100 | | | | | |

- Ô trống = **chưa quan sát được** (NULL), khác với 0% = có dữ liệu nhưng không ai mua. Lưới được sinh bằng `generate_series` chỉ tới `months_observed`.
- Heatmap: [docs/evidence/03-cohort.png](../docs/evidence/03-cohort.png), vẽ bằng [scripts/cohort_heatmap.py](../scripts/cohort_heatmap.py).
- Nhận xét: [docs/reflection_03.md](../docs/reflection_03.md) – cohort 03 giữ chân tốt nhất ở M1/M2, cohort 01 ổn định nhất; retention gần như phẳng (~45–50%) có thể là đặc điểm dữ liệu sinh ngẫu nhiên.

### 2.1 Bonus – RFM score & segment
- Chấm điểm 1–5 bằng `CEIL(5 × CUME_DIST())` thay vì `NTILE(5)` → khách có cùng giá trị luôn cùng điểm.
- `rfm_segment` = chuỗi 3 ký tự (tối đa 125 segment), gom thành nhóm hành động: *Champions, Loyal, At Risk, Hibernating…*
- LTV đơn giản = AOV × frequency.
- Kết quả: [docs/evidence/03-rfm-segments.csv](../docs/evidence/03-rfm-segments.csv).

### 2.2 Bonus – Time series
- **TS1**: doanh thu tháng + MoM growth bằng `LAG()`; kèm doanh thu TB/ngày để so công bằng giữa tháng dài/ngắn.
- **TS2**: doanh thu ngày + moving average 7/30 ngày; dùng `generate_series` lấp ngày trống để frame `ROWS` đúng nghĩa ngày lịch.
- Nhận xét ([03-timeseries.txt](../docs/evidence/03-timeseries.txt)): tháng 03 tăng mạnh nhất (+27,48% MoM); tháng 04 giảm thật mạnh nhất (−10,41%/ngày); tháng 06 thực chất đi ngang.

## 6.5 Hiệu năng & index

Báo cáo đầy đủ: [docs/explain_output/02-explain.md](../docs/explain_output/02-explain.md).

Query đo: BQ1 (doanh thu completed 1 tháng) – `WHERE order_status = … AND order_date BETWEEN …`, `SUM(order_total)`.

| | A – Không index | B – 2 index 1 cột | C – Composite covering |
|---|---|---|---|
| Kiểu scan | Seq Scan | Bitmap Heap Scan | **Index Only Scan** |
| Điều kiện vào Index Cond | 0/3 | 1/3 | **3/3** |
| Rows Removed by Filter | 4.374 | 169 | **0** |
| Buffers | 78 | 83 | **6** |
| Execution time (median) | 0,269 ms | 0,199 ms | **0,100 ms** |

Ở quy mô 2 triệu dòng (bảng thử nghiệm `perf_lab.orders_big`, xoá sau khi đo): **39,05 ms → 9,58 ms (nhanh 4,1×, đọc ít 53× block)**.

**Bài học rút ra**
1. Index làm query **đọc ít đi**, thời gian chỉ là hệ quả.
2. Composite index: cột lọc `=` đặt trước, cột lọc range đặt sau.
3. `INCLUDE (order_total)` biến index thành **covering index** → `Heap Fetches: 0`, đổi lại index to hơn ~23%.
4. Script đo idempotent: dùng `BEGIN; DROP INDEX …; ROLLBACK;` vì DDL của PostgreSQL có tính transaction.
