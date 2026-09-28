-- ============================================================
-- Buổi 3 — 1.1 CTE Refactoring (CTE1 .. CTE5)
-- Schema: core (xem sql/student/01_create_oltp.sql)
-- Quy ước KPI (docs/business_requirements.md): spending / revenue = SUM(order_total)
--   của các order 'completed'. Tháng tính theo giờ Asia/Ho_Chi_Minh.
-- Mọi bước trung gian viết bằng WITH ... AS, không dùng subquery thay CTE.
-- ============================================================

-- CTE1: Top 10 customer theo total spending
-- CTE customer_spending gom SUM(order_total) mỗi customer; SELECT ngoài chỉ sắp xếp + lấy top 10.
WITH customer_spending AS (
    SELECT customer_id,
           COUNT(*)         AS order_count,
           SUM(order_total) AS total_spending
    FROM core.orders
    WHERE order_status = 'completed'
    GROUP BY customer_id
)
SELECT cs.customer_id,
       c.full_name,
       cs.order_count,
       cs.total_spending
FROM customer_spending cs
JOIN core.customers c ON c.customer_id = cs.customer_id
ORDER BY cs.total_spending DESC, cs.customer_id
LIMIT 10;

-- CTE2: Phân tầng spending Low / Medium / High
-- Ngưỡng đề bài Low < 500, Medium 500-2000, High > 2000 tính theo USD; dữ liệu là VND nên quy đổi
-- 1 USD = 25,000 VND -> Low < 12,500,000 | Medium 12,500,000-50,000,000 | High > 50,000,000.
-- Ngưỡng đặt trong CTE params để đổi một chỗ. LEFT JOIN từ customers để khách chưa có đơn
-- completed vẫn được tính (spending = 0 -> Low).
WITH params AS (
    SELECT 12500000::numeric AS low_max,
           50000000::numeric AS medium_max
),
customer_spending AS (
    SELECT c.customer_id,
           COALESCE(SUM(o.order_total), 0) AS total_spending
    FROM core.customers c
    LEFT JOIN core.orders o
           ON o.customer_id = c.customer_id
          AND o.order_status = 'completed'
    GROUP BY c.customer_id
),
customer_tier AS (
    SELECT cs.customer_id,
           cs.total_spending,
           CASE
               WHEN cs.total_spending <  p.low_max    THEN 'Low'
               WHEN cs.total_spending <= p.medium_max THEN 'Medium'
               ELSE 'High'
           END AS spending_tier
    FROM customer_spending cs
    CROSS JOIN params p
)
SELECT spending_tier,
       COUNT(*)                                            AS customer_count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)  AS customer_pct,
       MIN(total_spending)                                 AS min_spending,
       MAX(total_spending)                                 AS max_spending,
       ROUND(AVG(total_spending), 2)                       AS avg_spending
FROM customer_tier
GROUP BY spending_tier
ORDER BY MIN(total_spending);

-- CTE3: Nested CTEs — orders_per_customer -> customer_stats
-- CTE thứ 2 đọc từ CTE thứ 1: đếm số order completed mỗi customer, rồi tính MIN/MAX/AVG
-- và phân bố số order trên toàn bộ tập customer.
WITH orders_per_customer AS (
    SELECT customer_id,
           COUNT(*) AS order_count
    FROM core.orders
    WHERE order_status = 'completed'
    GROUP BY customer_id
),
customer_stats AS (
    SELECT COUNT(*)                                                     AS customer_count,
           MIN(order_count)                                             AS min_orders,
           MAX(order_count)                                             AS max_orders,
           ROUND(AVG(order_count), 2)                                   AS avg_orders,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY order_count)     AS median_orders,
           COUNT(*) FILTER (WHERE order_count = 1)                      AS one_time_customers
    FROM orders_per_customer
)
SELECT customer_count,
       min_orders,
       max_orders,
       avg_orders,
       median_orders,
       one_time_customers,
       ROUND(100.0 * one_time_customers / customer_count, 2) AS one_time_pct
FROM customer_stats;

-- CTE4: AOV (Average Order Value) mỗi customer = total_spending / order_count
-- NULLIF chống chia 0 (an toàn dù CTE chỉ chứa customer có >= 1 order).
WITH customer_orders AS (
    SELECT customer_id,
           COUNT(*)         AS order_count,
           SUM(order_total) AS total_spending
    FROM core.orders
    WHERE order_status = 'completed'
    GROUP BY customer_id
),
customer_aov AS (
    SELECT customer_id,
           order_count,
           total_spending,
           ROUND(total_spending / NULLIF(order_count, 0), 2) AS aov
    FROM customer_orders
)
SELECT customer_id,
       order_count,
       total_spending,
       aov
FROM customer_aov
ORDER BY aov DESC, customer_id;

-- CTE5: Retention đơn giản theo cohort — % khách quay lại ở tháng SAU tháng mua đầu tiên
-- Chuỗi CTE: customer_orders (customer × tháng mua) -> cohort (tháng mua đầu = cohort_month)
--            -> later_orders (đơn ở tháng > cohort_month) -> data_range (tháng cuối có dữ liệu).
-- Định nghĩa: khách "quay lại" nếu có ít nhất 1 đơn completed ở BẤT KỲ tháng nào sau cohort_month.
-- LEFT JOIN cohort -> later_orders: khách không quay lại vẫn còn dòng (lo.customer_id NULL),
--   nhờ vậy COUNT(*) = cohort_size còn COUNT(lo.customer_id) = số khách quay lại (COUNT cột bỏ qua NULL).
-- months_observed cho biết cohort đó được quan sát bao nhiêu tháng tiếp theo: cohort của tháng
--   cuối cùng (2026-06) có months_observed = 0 nên retention 0% là hệ quả của cửa sổ dữ liệu,
--   không phải khách kém trung thành -> đọc số phải xem cột này.
WITH customer_orders AS (
    SELECT customer_id,
           DATE_TRUNC('month', order_date AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS order_month
    FROM core.orders
    WHERE order_status = 'completed'
),
cohort AS (
    SELECT customer_id,
           MIN(order_month) AS cohort_month
    FROM customer_orders
    GROUP BY customer_id
),
later_orders AS (
    SELECT co.customer_id,
           MIN(co.order_month) AS first_return_month
    FROM customer_orders co
    JOIN cohort ch ON ch.customer_id = co.customer_id
    WHERE co.order_month > ch.cohort_month
    GROUP BY co.customer_id
),
data_range AS (
    SELECT MAX(order_month) AS last_month
    FROM customer_orders
)
SELECT TO_CHAR(ch.cohort_month, 'YYYY-MM')                          AS cohort_month,
       COUNT(*)                                                     AS cohort_size,
       COUNT(lo.customer_id)                                        AS returned_customers,
       ROUND(100.0 * COUNT(lo.customer_id) / COUNT(*), 2)           AS retention_pct,
       (DATE_PART('year',  dr.last_month) - DATE_PART('year',  ch.cohort_month)) * 12
     + (DATE_PART('month', dr.last_month) - DATE_PART('month', ch.cohort_month)) AS months_observed
FROM cohort ch
LEFT JOIN later_orders lo ON lo.customer_id = ch.customer_id
CROSS JOIN data_range dr
GROUP BY ch.cohort_month, dr.last_month
ORDER BY ch.cohort_month;

-- ============================================================
-- Buổi 3 — 1.2 Window Functions (W1 .. W5)
-- Schema: core. Cột tiền của order trong DB tên là orders.order_total
--   (đề bài gọi là total_amount) — dùng order_total cho đúng DDL 01_create_oltp.sql.
-- Quy ước KPI (docs/business_requirements.md): chỉ tính order 'completed',
--   giữ nguyên cho cả 5 query để số liệu so sánh được với phần CTE ở trên.
-- Khác biệt cốt lõi so với GROUP BY: window function KHÔNG gộp dòng —
--   mỗi dòng gốc vẫn còn, chỉ thêm cột tính trên "khung cửa sổ" do OVER() mô tả.
-- ============================================================

-- W1: ROW_NUMBER() OVER (ORDER BY total_spending DESC) — xếp hạng customer theo tổng chi tiêu
-- OVER() không có PARTITION BY -> cửa sổ = TOÀN BỘ tập customer, đánh số 1..N liên tục.
-- ROW_NUMBER luôn duy nhất: hai customer chi tiêu bằng nhau vẫn nhận 2 số khác nhau,
-- thứ tự giữa họ do customer_id trong ORDER BY quyết định (thêm để kết quả ổn định giữa các lần chạy).
WITH customer_spending AS (
    SELECT customer_id,
           COUNT(*)         AS order_count,
           SUM(order_total) AS total_spending
    FROM core.orders
    WHERE order_status = 'completed'
    GROUP BY customer_id
)
SELECT ROW_NUMBER() OVER (ORDER BY cs.total_spending DESC, cs.customer_id) AS spending_rank,
       cs.customer_id,
       c.full_name,
       cs.order_count,
       cs.total_spending
FROM customer_spending cs
JOIN core.customers c ON c.customer_id = cs.customer_id
ORDER BY spending_rank
LIMIT 10;

-- W2: RANK() vs DENSE_RANK() — top 3 customer (đồng hạng thì RANK nhảy số, DENSE_RANK thì không)
-- KHÁC BIỆT:
--   ROW_NUMBER  : 1,2,3,4,5   — luôn duy nhất, bỏ qua chuyện bằng nhau.
--   RANK        : 1,1,3,4,4,6 — các dòng bằng nhau nhận CÙNG hạng, rồi NHẢY một khoảng
--                 đúng bằng số dòng đồng hạng (2 người hạng 1 -> người kế tiếp là hạng 3, mất hạng 2).
--   DENSE_RANK  : 1,1,2,3,3,4 — cũng cùng hạng khi bằng nhau nhưng KHÔNG để lại lỗ hổng,
--                 hạng kế tiếp luôn +1. Dùng khi muốn lấy "3 mức giá trị cao nhất".
-- Chọn tiêu chí order_count để xếp hạng vì ở đây mới thấy được sự khác biệt: total_spending
-- có 969 giá trị khác nhau trên 973 customer (gần như không đồng hạng) nên RANK và DENSE_RANK
-- sẽ ra số y hệt nhau; còn order_count chỉ có 12 giá trị -> đồng hạng hàng loạt, gap của RANK lộ rõ.
-- Lọc theo DENSE_RANK() = "top 3 mức số đơn cao nhất" (nếu lọc bằng RANK() <= 3 thì khi
-- mức cao nhất đã có >= 3 người, các mức sau sẽ bị cắt mất hoàn toàn).
-- Lấy tới dns <= 4 (giới hạn 9 dòng) để NHÌN THẤY cú nhảy: 4 người cùng 10 đơn đều là rank 3,
-- người tiếp theo (9 đơn) bị RANK đẩy thẳng lên 7 — mất hạng 4,5,6 — trong khi DENSE_RANK chỉ là 4.
-- Top 3 theo yêu cầu = các dòng có dense_rank_by_orders <= 3 (6 dòng đầu).
-- Lưu ý cú pháp: không lọc window function ở WHERE được (window chạy SAU WHERE) -> phải bọc thêm 1 CTE.
WITH customer_spending AS (
    SELECT customer_id,
           COUNT(*)         AS order_count,
           SUM(order_total) AS total_spending
    FROM core.orders
    WHERE order_status = 'completed'
    GROUP BY customer_id
),
customer_ranked AS (
    SELECT customer_id,
           order_count,
           total_spending,
           ROW_NUMBER() OVER (ORDER BY order_count DESC, customer_id) AS rn,
           RANK()       OVER (ORDER BY order_count DESC)              AS rnk,
           DENSE_RANK() OVER (ORDER BY order_count DESC)              AS dns
    FROM customer_spending
)
SELECT cr.rn,
       cr.rnk AS rank_by_orders,
       cr.dns AS dense_rank_by_orders,
       cr.customer_id,
       c.full_name,
       cr.order_count,
       cr.total_spending
FROM customer_ranked cr
JOIN core.customers c ON c.customer_id = cr.customer_id
WHERE cr.dns <= 4
  AND cr.rn  <= 9
ORDER BY cr.rn;

-- W3: ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date) — số thứ tự order của mỗi customer
-- PARTITION BY customer_id = chia dữ liệu thành từng nhóm theo customer, bộ đếm RESET về 1
-- ở mỗi customer mới; ORDER BY order_date quyết định đơn nào là thứ 1, thứ 2...
-- order_seq = 1 chính là đơn đầu tiên -> đây là nền để dựng cohort (CTE5) sau này.
-- COUNT(*) OVER (PARTITION BY customer_id) — cùng partition nhưng KHÔNG có ORDER BY
-- nên tính trên cả nhóm: tổng số đơn của customer đó, lặp lại trên mọi dòng của họ.
WITH customer_orders AS (
    SELECT order_id,
           customer_id,
           order_date,
           order_total
    FROM core.orders
    WHERE order_status = 'completed'
)
SELECT customer_id,
       order_id,
       (order_date AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS order_day,
       order_total,
       ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS order_seq,
       COUNT(*)     OVER (PARTITION BY customer_id)                               AS total_orders_of_customer
FROM customer_orders
ORDER BY customer_id, order_seq
LIMIT 10;

-- W4: LAG() / LEAD() — so sánh order_total với đơn TRƯỚC và đơn SAU của cùng customer
-- LAG(col)  = giá trị cột đó ở dòng LÙI 1 bậc trong cửa sổ (đơn liền trước của chính customer này).
-- LEAD(col) = giá trị ở dòng TIẾN 1 bậc (đơn liền sau).
-- Đơn đầu tiên không có đơn trước -> LAG trả NULL; đơn cuối cùng -> LEAD trả NULL.
-- Vì đã PARTITION BY customer_id nên LAG/LEAD không bao giờ "nhảy" sang customer khác.
-- Cột chênh lệch: diff_vs_prev = order_total - đơn trước (dương = lần này chi nhiều hơn lần trước),
-- pct_vs_prev = % thay đổi, NULLIF chống chia 0.
-- WINDOW w AS (...) khai báo cửa sổ 1 lần rồi dùng lại (OVER w) cho gọn thay vì lặp 6 lần.
WITH customer_orders AS (
    SELECT order_id,
           customer_id,
           order_date,
           order_total
    FROM core.orders
    WHERE order_status = 'completed'
)
SELECT customer_id,
       order_id,
       (order_date AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS order_day,
       order_total,
       LAG(order_total)  OVER w                AS prev_amount,
       order_total - LAG(order_total)  OVER w  AS diff_vs_prev,
       ROUND(100.0 * (order_total - LAG(order_total) OVER w)
             / NULLIF(LAG(order_total) OVER w, 0), 2)     AS pct_vs_prev,
       LEAD(order_total) OVER w                AS next_amount,
       LEAD(order_total) OVER w - order_total  AS diff_to_next,
       CASE
           WHEN LAG(order_total) OVER w IS NULL       THEN 'first_order'
           WHEN order_total > LAG(order_total) OVER w THEN 'up'
           WHEN order_total < LAG(order_total) OVER w THEN 'down'
           ELSE 'flat'
       END AS trend_vs_prev
FROM customer_orders
WINDOW w AS (PARTITION BY customer_id ORDER BY order_date, order_id)
ORDER BY customer_id, order_date, order_id
LIMIT 10;

-- W5: SUM(order_total) OVER (ORDER BY order_date) — running total (doanh thu luỹ kế)
-- OVER có ORDER BY nhưng không PARTITION BY -> cộng dồn từ đơn đầu tiên đến đơn hiện tại
-- trên toàn bộ tập dữ liệu.
-- KHUNG (frame): mặc định khi có ORDER BY là RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW,
-- nghĩa là mọi dòng CÙNG order_date (peer) đều nhận cùng một giá trị luỹ kế -> nhìn như bị "đứng số".
-- Ở đây ghi rõ ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW để cộng dồn theo TỪNG DÒNG,
-- kèm order_id trong ORDER BY cho thứ tự xác định.
-- SUM(order_total) OVER () (không ORDER BY, không PARTITION) = tổng doanh thu toàn bộ,
-- dùng làm mẫu số cho running_pct_of_total -> % doanh thu đã tích luỹ tới dòng hiện tại.
WITH completed_orders AS (
    SELECT order_id,
           customer_id,
           order_date,
           order_total
    FROM core.orders
    WHERE order_status = 'completed'
)
SELECT order_id,
       customer_id,
       (order_date AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS order_day,
       order_total,
       SUM(order_total) OVER (ORDER BY order_date, order_id
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_revenue,
       ROUND(100.0 * SUM(order_total) OVER (ORDER BY order_date, order_id
                                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / SUM(order_total) OVER (), 4) AS running_pct_of_total
FROM completed_orders
ORDER BY order_date, order_id
LIMIT 10;

-- ============================================================
-- 1.3 Customer Analytics — RFM (Recency, Frequency, Monetary) trong 1 bảng
-- ============================================================

-- RFM: 1 dòng / customer với 4 cột customer_id, recency_days, frequency, monetary
--   recency_days = NOW() - MAX(order_date), lấy phần số ngày tròn (số ngày từ đơn cuối tới hiện tại)
--   frequency    = COUNT(order_id)
--   monetary     = SUM(order_total)
-- Chỉ tính đơn 'completed' (cùng quy ước KPI với CTE1-CTE5 và docs/business_requirements.md):
--   đơn cancelled/pending chưa phát sinh doanh thu nên không được tính vào F và M.
-- Cách chọn: 1 GROUP BY duy nhất thay vì 3 CTE (recency / frequency / monetary) rồi JOIN lại.
--   Cả 3 metrics cùng grain (customer_id) và cùng nguồn (core.orders đã lọc completed), nên
--   MAX / COUNT / SUM tính được trong 1 lần quét bảng; tách 3 CTE sẽ quét 3 lần và thêm 2 JOIN
--   mà kết quả y hệt. CTE completed_orders chỉ để tách phần lọc cho dễ đọc.
-- Dùng INNER (không LEFT JOIN từ customers): khách chưa có đơn completed không có recency hợp lệ
--   và sẽ ra NULL ở frequency/monetary -> loại khỏi bảng RFM (đề yêu cầu không NULL).
-- Mọi order_date đều ở quá khứ nên recency_days >= 0; GREATEST(..., 0) chỉ là chốt an toàn
--   nếu có đơn ghi lệch giờ tương lai. Giá trị recency thay đổi theo thời điểm chạy (NOW()).
WITH completed_orders AS (
    SELECT order_id,
           customer_id,
           order_date,
           order_total
    FROM core.orders
    WHERE order_status = 'completed'
)
SELECT customer_id,
       GREATEST(EXTRACT(DAY FROM NOW() - MAX(order_date))::int, 0) AS recency_days,
       COUNT(order_id)                                             AS frequency,
       SUM(order_total)                                            AS monetary
FROM completed_orders
GROUP BY customer_id
ORDER BY customer_id;

-- ============================================================
-- 1.4 Cohort Analysis — Retention theo tháng (ma trận cohort × M0..M5)
-- ============================================================

-- Cohort: hàng = cohort_month, cột = số tháng kể từ tháng mua đầu (M0, M1, M2...), giá trị = %
--   cohort_month = DATE_TRUNC('month', MIN(order_date)) của customer (chỉ đơn 'completed',
--                  tháng theo giờ Asia/Ho_Chi_Minh — cùng quy ước với CTE5 / RFM).
--   mN           = % customer của cohort có >= 1 đơn completed ở ĐÚNG tháng cohort_month + N.
--                  M0 luôn 100% (tháng mua đầu). Khác CTE5 ("quay lại bất kỳ tháng nào sau"):
--                  ở đây tính riêng từng tháng, nên M1, M2... không cộng dồn và có thể lên/xuống.
-- Chuỗi CTE:
--   customer_months -> (customer, tháng có mua) DISTINCT: mua 3 đơn trong 1 tháng vẫn tính 1 lần.
--   cohort          -> tháng mua đầu mỗi customer.
--   activity        -> month_offset = số tháng giữa tháng mua và cohort_month (dùng AGE để
--                      đúng cả khi qua năm: năm*12 + tháng).
--   cohort_size     -> mẫu số: số customer mỗi cohort.
--   offsets         -> lưới cohort × offset 0..months_observed (generate_series). Chỉ sinh các
--                      ô ĐÃ quan sát được, nên ô tương lai (vd cohort 2026-05 ở M2) ra NULL = "chưa
--                      có dữ liệu", phân biệt với 0% = "có dữ liệu nhưng không ai mua".
--   retention       -> LEFT JOIN lưới với số khách active -> COALESCE về 0 cho ô quan sát được.
-- Pivot bằng MAX(...) FILTER (WHERE month_offset = N): mỗi cột lấy đúng 1 ô của cohort.
WITH customer_months AS (
    SELECT DISTINCT
           customer_id,
           DATE_TRUNC('month', order_date AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS order_month
    FROM core.orders
    WHERE order_status = 'completed'
),
cohort AS (
    SELECT customer_id,
           MIN(order_month) AS cohort_month
    FROM customer_months
    GROUP BY customer_id
),
activity AS (
    SELECT ch.cohort_month,
           cm.customer_id,
           (EXTRACT(YEAR  FROM AGE(cm.order_month, ch.cohort_month)) * 12
          + EXTRACT(MONTH FROM AGE(cm.order_month, ch.cohort_month)))::int AS month_offset
    FROM customer_months cm
    JOIN cohort ch ON ch.customer_id = cm.customer_id
),
cohort_size AS (
    SELECT cohort_month,
           COUNT(*) AS cohort_size
    FROM cohort
    GROUP BY cohort_month
),
data_range AS (
    SELECT MAX(order_month) AS last_month
    FROM customer_months
),
offsets AS (
    SELECT cs.cohort_month,
           cs.cohort_size,
           gs.month_offset
    FROM cohort_size cs
    CROSS JOIN data_range dr
    CROSS JOIN LATERAL generate_series(
               0,
               (EXTRACT(YEAR  FROM AGE(dr.last_month, cs.cohort_month)) * 12
              + EXTRACT(MONTH FROM AGE(dr.last_month, cs.cohort_month)))::int
           ) AS gs(month_offset)
),
retention AS (
    SELECT o.cohort_month,
           o.cohort_size,
           o.month_offset,
           COUNT(a.customer_id)                                   AS active_customers,
           ROUND(100.0 * COUNT(a.customer_id) / o.cohort_size, 2) AS retention_pct
    FROM offsets o
    LEFT JOIN activity a
           ON a.cohort_month = o.cohort_month
          AND a.month_offset = o.month_offset
    GROUP BY o.cohort_month, o.cohort_size, o.month_offset
)
SELECT TO_CHAR(cohort_month, 'YYYY-MM')                     AS cohort_month,
       MAX(retention_pct) FILTER (WHERE month_offset = 0)   AS m0,
       MAX(retention_pct) FILTER (WHERE month_offset = 1)   AS m1,
       MAX(retention_pct) FILTER (WHERE month_offset = 2)   AS m2,
       MAX(retention_pct) FILTER (WHERE month_offset = 3)   AS m3,
       MAX(retention_pct) FILTER (WHERE month_offset = 4)   AS m4,
       MAX(retention_pct) FILTER (WHERE month_offset = 5)   AS m5,
       MAX(cohort_size)                                     AS cohort_size
FROM retention
GROUP BY cohort_month
ORDER BY cohort_month;
