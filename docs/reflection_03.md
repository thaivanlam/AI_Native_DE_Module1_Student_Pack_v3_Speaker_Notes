# Reflection 03 — Cohort Retention

Nguồn: `docs/cohort_retention.csv`, heatmap `docs/evidence/03-cohort.png` (query `-- Cohort` trong `sql/student/03_cte_window_cohort.sql`).

- **Cohort 2026-03 giữ chân tốt nhất ở giai đoạn đầu**: M1 = 52.53%, M2 = 51.90%, cao nhất ở cả hai cột. Mình so theo cùng một cột M1/M2 chứ không so % tổng, vì cohort cũ hơn được quan sát lâu hơn nên dễ trông "tốt" hơn.
- **Cohort 2026-01 ổn định nhất về dài hạn**: từ M1 đến M5 luôn nằm trong khoảng 45–50%, không có tháng nào tụt mạnh. Đây cũng là cohort lớn nhất (479 khách), nên con số này đáng tin hơn cả.
- **Cohort 2026-05 yếu nhất** (M1 = 38.10%). Tuy nhiên cohort này chỉ có 42 khách, 1 khách đã tương đương 2.4 điểm %. Cohort 2026-04 (60 khách) và 2026-06 (15 khách, chưa có M1) cũng quá nhỏ để kết luận.
- **Vì sao?** Dữ liệu không có thông tin về kênh, khuyến mãi hay sản phẩm của đơn đầu, nên chưa thể chứng minh nguyên nhân. Giả thuyết: khách đầu năm (01–03) là tập khách "gốc" có nhu cầu mua lặp lại, còn các cohort sau nhỏ dần, có thể là khách vãng lai. Muốn kiểm chứng cần JOIN thêm sản phẩm hoặc danh mục của đơn đầu tiên theo từng cohort.
- **Điểm lạ**: retention gần như phẳng (~45–50%) chứ không giảm dần theo thời gian như đường cong thường gặp. Mình đoán đây là đặc điểm của bộ dữ liệu sinh ngẫu nhiên, không nên coi là hành vi thật của khách hàng.
