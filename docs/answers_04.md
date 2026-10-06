# 1.4 KPI Queries từ Data Mart — Đáp án

- **Nguồn dữ liệu:** PostgreSQL `ecommerce`, schema `mart` (container `ecommerce-postgres`) — chỉ đọc `fact_sales` JOIN các dimension, không JOIN bảng OLTP.
- **File SQL:** [`sql/student/04_kpi_from_mart.sql`](../sql/student/04_kpi_from_mart.sql) (KPI1–KPI5)
- **Output chạy lại:** [`docs/evidence/04-kpi-results.txt`](evidence/04-kpi-results.txt)
- **Quy ước (theo [business_requirements.md](business_requirements.md)):** Revenue = doanh thu net của order `completed` = `SUM(fact_sales.revenue)`, lọc trạng thái qua `dim_order_status` vì mart nạp tất cả trạng thái đơn. Grain của fact là dòng hàng nên đếm đơn bằng `COUNT(DISTINCT order_id)`. Tháng tính theo giờ `Asia/Ho_Chi_Minh` (đã quy đổi lúc load `dim_date`). Đơn vị tiền: VND.

## Tóm tắt

| # | KPI | Đáp án |
|---|---|---|
| 1 | Total revenue by month | 6 tháng, tổng **48,077,944,000 VND**; cao nhất tháng 3: **8,998,721,500 VND** |
| 2 | Revenue by category | 15 category; đứng đầu **Skincare – 4,776,238,500 VND (9.93%)** |
| 3 | Top 10 products theo revenue | Top 1 **PRD000297 – Product 297 Cell – 302,895,000 VND** |
| 4 | AOV | **12,391,222.68 VND** (48,077,944,000 / 3,880 đơn) |
| 5 | Customer count by segment/region | **973 khách** có đơn completed; Standard 549, Silver 233, Gold 147, Platinum 44 |

---

## KPI1. Total revenue by month

```sql
SELECT d.year,
       d.month,
       d.month_name,
       COUNT(DISTINCT f.order_id) AS completed_orders,
       SUM(f.revenue)             AS total_revenue
FROM mart.fact_sales f
JOIN mart.dim_date d ON d.date_key = f.date_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;
```

**Đáp án:**

| Năm | Tháng | Số đơn completed | Total revenue (VND) |
|---|---|---|---|
| 2026 | 1 – January | 654 | 8,231,711,000 |
| 2026 | 2 – February | 590 | 7,058,655,000 |
| 2026 | 3 – March | 712 | 8,998,721,500 |
| 2026 | 4 – April | 623 | 7,801,828,500 |
| 2026 | 5 – May | 675 | 8,230,727,000 |
| 2026 | 6 – June | 626 | 7,756,301,000 |
| | **Tổng** | **3,880** | **48,077,944,000** |

**Nhận xét:** Doanh thu dao động 7.1–9.0 tỷ/tháng, đỉnh ở tháng 3 và đáy ở tháng 2 (tháng ngắn nhất); tổng 6 tháng khớp đúng doanh thu completed bên OLTP (48,077,944,000).

---

## KPI2. Revenue by category

```sql
SELECT p.parent_category,
       p.category,
       SUM(f.quantity)            AS units_sold,
       SUM(f.revenue)             AS total_revenue,
       ROUND(100.0 * SUM(f.revenue) / SUM(SUM(f.revenue)) OVER (), 2) AS revenue_pct
FROM mart.fact_sales f
JOIN mart.dim_product p ON p.product_key = f.product_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY p.parent_category, p.category
ORDER BY total_revenue DESC, p.category;
```

**Đáp án:**

| # | Danh mục cha | Category | Số lượng bán | Total revenue (VND) | Tỷ trọng |
|---|---|---|---|---|---|
| 1 | Beauty | Skincare | 1,217 | 4,776,238,500 | 9.93% |
| 2 | Home & Living | Kitchen | 1,163 | 4,192,039,000 | 8.72% |
| 3 | Electronics | Phones | 967 | 3,818,082,500 | 7.94% |
| 4 | Sports | Fitness | 819 | 3,648,597,000 | 7.59% |
| 5 | Beauty | Personal Care | 818 | 3,518,033,500 | 7.32% |
| 6 | Home & Living | Home Decor | 978 | 3,289,578,000 | 6.84% |
| 7 | Books | Technology | 962 | 3,020,981,000 | 6.28% |
| 8 | Beauty | Makeup | 946 | 3,013,922,500 | 6.27% |
| 9 | Sports | Outdoor | 879 | 2,873,363,500 | 5.98% |
| 10 | Sports | Sportswear | 685 | 2,816,603,500 | 5.86% |
| 11 | Electronics | Computers | 871 | 2,810,318,000 | 5.85% |
| 12 | Electronics | Accessories | 771 | 2,809,430,000 | 5.84% |
| 13 | Home & Living | Furniture | 727 | 2,726,178,000 | 5.67% |
| 14 | Books | Business | 660 | 2,460,435,500 | 5.12% |
| 15 | Books | Lifestyle | 566 | 2,304,143,500 | 4.79% |

**Nhận xét:** Skincare dẫn đầu với 9.93% doanh thu nhưng không category nào vượt 10% — doanh thu phân tán khá đều trên 15 category, không phụ thuộc vào một nhóm hàng.

---

## KPI3. Top 10 products theo revenue

```sql
SELECT p.product_id,
       p.product_name,
       p.category,
       SUM(f.quantity) AS units_sold,
       SUM(f.revenue)  AS total_revenue
FROM mart.fact_sales f
JOIN mart.dim_product p ON p.product_key = f.product_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY p.product_id, p.product_name, p.category
ORDER BY total_revenue DESC, p.product_id
LIMIT 10;
```

**Đáp án:**

| # | Product | Tên | Category | Số lượng bán | Total revenue (VND) |
|---|---|---|---|---|---|
| 1 | PRD000297 | Product 297 Cell | Skincare | 40 | 302,895,000 |
| 2 | PRD000309 | Product 309 Ability | Home Decor | 43 | 297,192,000 |
| 3 | PRD000203 | Product 203 Environment | Phones | 36 | 260,936,000 |
| 4 | PRD000300 | Product 300 Term | Sportswear | 35 | 259,776,000 |
| 5 | PRD000173 | Product 173 Trade | Skincare | 35 | 248,452,500 |
| 6 | PRD000268 | Product 268 Stuff | Accessories | 33 | 247,468,500 |
| 7 | PRD000204 | Product 204 Realize | Phones | 34 | 238,183,000 |
| 8 | PRD000126 | Product 126 One | Personal Care | 35 | 236,880,000 |
| 9 | PRD000238 | Product 238 Character | Fitness | 33 | 233,859,500 |
| 10 | PRD000084 | Product 084 Job | Home Decor | 32 | 233,227,500 |

**Nhận xét:** Top 1 là PRD000297 (Skincare) với 302,895,000 VND; cả top 10 cộng lại chỉ khoảng 2.56 tỷ, tức hơn 5% tổng doanh thu trên 500 sản phẩm — không có sản phẩm "ngôi sao" áp đảo.

---

## KPI4. AOV (Average Order Value)

```sql
SELECT SUM(f.revenue)             AS total_revenue,
       COUNT(DISTINCT f.order_id) AS completed_orders,
       ROUND(SUM(f.revenue) / COUNT(DISTINCT f.order_id), 2) AS aov
FROM mart.fact_sales f
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed';
```

**Đáp án:** **AOV = 12,391,222.68 VND** (48,077,944,000 VND / 3,880 đơn completed).

**Nhận xét:** Trùng khớp với AOV tính trên OLTP ở Buổi 2 (12,391,222.68 VND) — mart cho cùng đáp án mà chỉ cần 1 JOIN; bắt buộc `COUNT(DISTINCT order_id)` vì 1 đơn có nhiều dòng fact.

---

## KPI5. Customer count by segment / region

**Theo segment:**

```sql
SELECT c.customer_segment,
       COUNT(DISTINCT f.customer_key) AS customer_count,
       COUNT(DISTINCT f.order_id)     AS completed_orders,
       SUM(f.revenue)                 AS total_revenue,
       ROUND(SUM(f.revenue) / COUNT(DISTINCT f.customer_key), 2) AS revenue_per_customer
FROM mart.fact_sales f
JOIN mart.dim_customer c ON c.customer_key = f.customer_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY c.customer_segment
ORDER BY total_revenue DESC;
```

**Đáp án:**

| Segment | Số khách | Số đơn completed | Total revenue (VND) | Revenue / khách (VND) |
|---|---|---|---|---|
| Standard | 549 | 2,255 | 28,241,059,000 | 51,440,908.93 |
| Silver | 233 | 899 | 10,975,640,000 | 47,105,751.07 |
| Gold | 147 | 571 | 6,854,916,500 | 46,632,085.03 |
| Platinum | 44 | 155 | 2,006,328,500 | 45,598,375.00 |
| **Tổng** | **973** | **3,880** | **48,077,944,000** | |

**Theo region (city) — KPI5b:**

```sql
SELECT c.city,
       COUNT(DISTINCT f.customer_key) AS customer_count,
       COUNT(DISTINCT f.order_id)     AS completed_orders,
       SUM(f.revenue)                 AS total_revenue
FROM mart.fact_sales f
JOIN mart.dim_customer c ON c.customer_key = f.customer_key
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
WHERE s.order_status = 'completed'
GROUP BY c.city
ORDER BY customer_count DESC, c.city;
```

| City | Số khách | Số đơn completed | Total revenue (VND) |
|---|---|---|---|
| Bac Ninh | 111 | 462 | 5,664,023,500 |
| Vinh | 110 | 421 | 5,354,184,500 |
| Ho Chi Minh City | 109 | 429 | 5,404,917,500 |
| Hai Phong | 97 | 365 | 4,549,735,500 |
| Can Tho | 94 | 409 | 4,785,581,500 |
| Da Nang | 94 | 372 | 4,707,089,000 |
| Hue | 94 | 352 | 4,302,904,500 |
| Nha Trang | 91 | 413 | 5,163,161,500 |
| Quang Ninh | 90 | 357 | 4,522,311,000 |
| Hanoi | 83 | 300 | 3,624,035,500 |

**Nhận xét:** 973/1,000 khách có ít nhất 1 đơn completed; Standard chiếm 549 khách và 58.7% doanh thu, còn doanh thu trên mỗi khách gần như ngang nhau giữa các segment (45.6–51.4 triệu) — segment hiện chưa phản ánh mức chi tiêu. Mart có cả `customer_segment` lẫn `city` nên làm được cả hai chiều, không cần phương án thay thế bằng `dim_order_status`.
