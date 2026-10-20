# B8 — Bài 4: Data Mart Integration & KPI Reconciliation

`src/refresh_mart.py` được gọi ở bước 7 của pipeline khi có `--refresh-mart`.
Module chạy `sql/solutions/12_load_data_mart.sql`, đo bốn KPI trước/sau và xuất
`docs/kpi_comparison.csv` với header `kpi,before,after,diff`.

```powershell
.\.venv\Scripts\python.exe -m src.pipeline --source file --input-dir data/incremental/day_2026-07-01 --refresh-mart
```

## Quy ước dữ liệu

- Dimension customer, product, payment method và order status được upsert theo
  natural key, giữ surrogate key cho các fact hiện hữu.
- Lịch gồm đủ 1.095 ngày từ 2025-01-01 đến 2027-12-31, thêm bằng
  `ON CONFLICT (date_key) DO NOTHING`. Ngày đơn hàng theo múi giờ Việt Nam;
  ngày ngoài lịch làm refresh thất bại và rollback.
- Fact có grain một `order_item_id`; chọn payment thành công mới nhất của mỗi
  đơn để tránh nhân dòng, dùng `unknown` khi chưa có payment thành công.
- Theo đề bài, fact dùng `ON CONFLICT (order_item_id) DO NOTHING`. Vì vậy các
  thay đổi giá, số lượng hoặc trạng thái của fact đã nạp cần quy trình rebuild
  riêng; lần refresh này chỉ thêm fact mới.
- `net_amount` là generated column bằng `revenue`, giữ tương thích với SQL KPI
  Buổi 4. Lần đầu chạy trên schema cũ đo Before bằng `revenue` rồi tự bổ sung
  `net_amount`; các lần sau đo bằng `SUM(net_amount)`.
- Doanh thu và số lượng tính trên mọi fact, gồm mọi trạng thái đơn.
  `order_count` và `completed_orders` đếm `DISTINCT order_id`, tránh đếm lặp
  đơn có nhiều dòng hàng; `completed_orders` lọc trạng thái `completed`.

Before phản ánh Mart đã công bố trước refresh; Core có thể đã được nạp ở bước 5.
Nếu chưa có Mart, Before bằng 0. Refresh chạy trong một transaction có advisory
lock, commit khi thành công, rollback khi lỗi và luôn đóng kết nối. CSV dùng
Decimal để giữ chính xác tiền và thay thế file atomically sau commit. Nếu ghi CSV
thất bại sau commit, pipeline báo lỗi và không tiến checkpoint; chạy lại an toàn
nhưng Before lúc đó là Mart đã commit.

## Minh chứng thực tế và cách tái hiện

```powershell
.\.venv\Scripts\python.exe -m scripts.demo_mart_reconciliation
.\.venv\Scripts\python.exe -m pytest -q
```

Script demo cần quyền CREATEDB, tạo database tạm, sao chép Core hiện tại rồi
loại các đơn của batch ngày 01/07/2026 khỏi bản sao để chuẩn bị baseline.
Script nạp Mart bằng SQL Buổi 4 để kiểm tra tương thích, chạy CLI `main()` với
`--refresh-mart`, đối soát trực tiếp với Core và chạy lại cùng batch để xác nhận
idempotency. Không giả lập các bước ETL hay kết nối database. Database tạm được
xóa trong `finally`; checkpoint và bảng Core/Mart đang cấu hình giữ nguyên.

`docs/evidence/08-mart-refresh.txt` ghi tên database tạm, SQL, log pipeline,
đối soát Core, lịch, kiểm tra trùng lặp và kết quả replay. CSV lưu kết quả lần
nạp gia tăng trước replay để giữ được mức tăng của batch:

| KPI | Before | After | Diff |
|---|---:|---:|---:|
| total_revenue | 61706432000.00 | 68932835500.00 | 7226403500.00 |
| order_count | 5000 | 5600 | 600 |
| completed_orders | 3880 | 4241 | 361 |
| total_items_sold | 16659 | 18578 | 1919 |

Chạy lại cùng batch cho cả bốn diff bằng 0. Chạy pipeline trực tiếp sau đó sẽ
thay thế CSV bằng kết quả của lần refresh mới nhất.
