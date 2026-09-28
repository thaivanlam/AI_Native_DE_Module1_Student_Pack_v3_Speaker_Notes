# Project Guide – E-commerce Data Platform (Module 1)

Bộ tài liệu giải thích project, đọc **từ tổng quan đến chi tiết**. Mỗi file trả lời một câu hỏi; đọc theo thứ tự để có bức tranh đầy đủ, hoặc nhảy thẳng tới phần cần.

| # | File | Trả lời câu hỏi | Mức độ |
|---|---|---|---|
| 1 | [01_tong_quan.md](01_tong_quan.md) | Project này là gì, giải quyết bài toán gì, gồm những giai đoạn nào? | Tổng quan |
| 2 | [02_kien_truc.md](02_kien_truc.md) | Dữ liệu đi qua những tầng nào, hạ tầng gồm những thành phần gì? | Tổng quan |
| 3 | [03_cau_truc_thu_muc.md](03_cau_truc_thu_muc.md) | Mỗi thư mục/file dùng để làm gì? | Trung bình |
| 4 | [04_du_lieu.md](04_du_lieu.md) | Có những dataset nào, quy ước dữ liệu ra sao, dữ liệu bẩn chứa lỗi gì? | Trung bình |
| 5 | [05_database_oltp.md](05_database_oltp.md) | Schema `core` được thiết kế thế nào: bảng, khoá, ràng buộc, index? | Chi tiết |
| 6 | [06_sql_analytics.md](06_sql_analytics.md) | Các truy vấn phân tích (KPI, CTE, window, RFM, cohort, hiệu năng) làm gì và cho kết quả gì? | Chi tiết |
| 7 | [07_data_mart.md](07_data_mart.md) | Sales Data Mart (schema `mart`) cần thiết kế ra sao? | Chi tiết |
| 8 | [08_python_pipeline.md](08_python_pipeline.md) | Pipeline Python gồm module nào, luồng xử lý end-to-end thế nào? | Chi tiết |
| 9 | [09_mock_api.md](09_mock_api.md) | Mock REST API hoạt động ra sao, gọi thế nào? | Chi tiết |
| 10 | [10_van_hanh.md](10_van_hanh.md) | Cài đặt, chạy, reset, nộp evidence, xử lý lỗi thường gặp? | Thực hành |
| 11 | [11_trang_thai.md](11_trang_thai.md) | Phần nào đã làm xong, phần nào còn TODO? | Tiến độ |

## Đọc nhanh trong 60 giây

- **Bài toán:** xây nền tảng dữ liệu cho một sàn E-commerce – từ yêu cầu nghiệp vụ tới một **daily pipeline tự động**.
- **Luồng chính:** `Business Requirement → ERD → PostgreSQL OLTP → SQL Analytics → Sales Data Mart → Python ingestion (file + API) → Data Quality → Daily Pipeline`.
- **Công nghệ:** PostgreSQL 16 và FastAPI chạy trong Docker; Python 3.11 (pandas, SQLAlchemy, requests, pytest).
- **Dữ liệu:** 7 thực thể (categories, customers, products, order_status, orders, order_items, payments); seed 5.000 đơn, batch sạch ngày 2026-07-01, batch bẩn ngày 2026-07-02.
- **Nguyên tắc:** không sửa RAW · chạy lại không nhân đôi dữ liệu · số liệu phải đối soát được · không hard-code secret.
- **Tiến độ hiện tại:** Buổi 1–3 (OLTP + SQL analytics + hiệu năng) đã hoàn thành kèm evidence; Buổi 4–8 (Data Mart, Python pipeline) vẫn là skeleton/TODO.

> Tài liệu này mô tả project ở trạng thái commit `ec423d2` (2026-09-28). Nguồn chính thức vẫn là [../README.md](../README.md) và các file trong `docs/`, `sql/`.
