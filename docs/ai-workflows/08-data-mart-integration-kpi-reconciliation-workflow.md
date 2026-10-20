# Workflow AI — Bài 4: Data Mart Integration & KPI Reconciliation

Tài liệu ghi lại cách AI xử lý Bài 4 trong [đề MD01-B8](../../assignments/MD01-B8_Bai-tap_Tu-dong-hoa-Daily-Pipeline-va-Tich-hop-End-to-End.md), từ khảo sát repository đến triển khai và kiểm chứng trên PostgreSQL thật. Kết quả được xác nhận ngày 20/10/2026.

## 1. Đọc yêu cầu và xác định khoảng trống

AI đọc riêng yêu cầu Bài 4, kiểm tra trạng thái Git, sau đó đọc các file liên quan:

- `src/refresh_mart.py`: SQL được gọi, transaction và vòng đời kết nối.
- `src/pipeline.py`: vị trí gọi refresh, cờ CLI và điều kiện ghi checkpoint.
- `sql/student/04_data_mart.sql`: schema Mart và quy ước dữ liệu từ Buổi 4.
- `src/config.py`, `src/database.py`: cấu hình đường dẫn và kết nối.
- `src/load_postgres.py`, `src/validators/`: cách nạp Core và kiểm tra dữ liệu.
- `tests/test_refresh_mart.py`, các test orchestration và checkpoint: hành vi phải giữ.
- Tài liệu dự án và minh chứng các bài trước: cách chạy môi trường hiện có.

Khảo sát cho thấy `refresh_mart()` đã có commit, rollback và đóng kết nối, nhưng đang chạy SQL Buổi 4 theo cách `TRUNCATE` rồi nạp lại toàn bộ Mart. Script `sql/solutions/12_load_data_mart.sql` mà đề yêu cầu chưa có. Mart dùng cột `revenue`, trong khi đề yêu cầu KPI từ `net_amount`; module cũng chưa xuất bảng Before/After.

| Yêu cầu | Quyết định triển khai |
|---|---|
| Chạy đúng script theo đề | Tạo `sql/solutions/12_load_data_mart.sql` |
| Làm mới 4 dimension | Upsert theo natural key, giữ surrogate key |
| Lịch cố định 2025–2027 | Sinh đủ 1.095 ngày, bỏ qua date_key đã có |
| Nạp fact không trùng | `ON CONFLICT (order_item_id) DO NOTHING` |
| Đo đủ 4 KPI | Truy vấn Mart trước và sau khi thực thi SQL |
| CSV chuẩn | Xuất `kpi,before,after,diff`, giữ độ chính xác tiền |
| Transaction an toàn | Commit thành công, rollback khi lỗi, luôn close |
| Minh chứng mức tăng thật | Chạy batch trên database tạm có baseline rõ ràng |

**Prompt có thể dùng lại:**

> Đọc riêng yêu cầu Bài 4 và mã liên quan. Kiểm tra Git trước khi sửa. Đối chiếu đường dẫn SQL, schema Mart, cách nạp hiện tại và đầu ra KPI; xác định phần thiếu và hành vi cần giữ tương thích.

## 2. Chọn cách tích hợp với mã hiện có

AI giữ điểm gọi `refresh_mart()` tại bước 7 của pipeline. Vì Core đã được nạp ở bước 5, Before được hiểu là KPI của Mart trước khi refresh; After là KPI của Mart sau khi bổ sung fact mới. Cách này cho phép đo phần dữ liệu vừa được đưa từ Core sang Mart mà không cần đổi thứ tự 8 bước.

Để đáp ứng `SUM(net_amount)` đồng thời giữ SQL Buổi 4 hoạt động, AI thêm `net_amount` dưới dạng generated column bằng `revenue`. Khi đọc Before trên schema cũ, module kiểm tra cột và dùng `revenue` nếu chưa có `net_amount`; script refresh bổ sung cột trước khi đo After.

AI cũng xác định giới hạn của `DO NOTHING`: fact đã tồn tại giữ nguyên số lượng, giá và khóa trạng thái. Đây là chính sách thêm mới theo đề bài; sửa giao dịch cũ cần quy trình rebuild hoặc chính sách cập nhật khác. Giới hạn này được ghi rõ trong tài liệu bàn giao.

**Prompt có thể dùng lại:**

> Thiết kế refresh gia tăng tương thích với schema Buổi 4. Làm rõ Before/After được đo ở đâu trong pipeline, cách giữ các query revenue cũ và ảnh hưởng của DO NOTHING đối với giao dịch đã nạp.

## 3. Triển khai SQL và module Python

### SQL nạp Mart

AI tái sử dụng cấu trúc bảng và index của Buổi 4, thay phần full refresh bằng các bước:

1. Tạo schema/bảng nếu chưa tồn tại và bổ sung generated column `net_amount`.
2. Sinh lịch từ `2025-01-01` đến `2027-12-31`, dùng `ON CONFLICT (date_key) DO NOTHING`.
3. Upsert customer, product, payment method và order status theo khóa nghiệp vụ.
4. Tạo payment method `unknown` cho đơn chưa có payment thành công.
5. Kiểm tra ngày đơn hàng ngoài lịch; nếu có thì phát sinh lỗi để rollback thay vì làm rơi fact.
6. Chọn một payment thành công mới nhất cho mỗi đơn bằng `DISTINCT ON`, tránh nhân dòng khi join.
7. Nạp fact từ `core.order_items`, `core.orders` và dimension; bỏ qua `order_item_id` đã có.

SQL không chứa `TRUNCATE` hoặc transaction boundary riêng; module Python quản lý transaction cho toàn bộ refresh.

### Module refresh và xuất KPI

Trong `src/refresh_mart.py`, AI triển khai trình tự:

1. Đọc script SQL và mở raw connection.
2. Lấy transaction advisory lock để các refresh không chạy SQL đồng thời.
3. Đo Before; nếu chưa có bảng fact thì dùng bộ KPI bằng 0.
4. Thực thi SQL, đo After rồi commit.
5. Khi lỗi database, rollback và truyền lỗi về pipeline; đóng kết nối trong `finally`.
6. Tính `diff = after - before`, ghi CSV qua file tạm rồi thay thế file đích.
7. Ghi log đường dẫn SQL, Before, After và diff của từng KPI.

Doanh thu dùng Decimal để tránh mất chính xác khi tính chênh lệch. Hai KPI đếm đơn dùng `COUNT(DISTINCT order_id)` vì một đơn có thể có nhiều dòng fact. `completed_orders` lọc trạng thái `completed`; doanh thu và số lượng cộng trên mọi fact theo yêu cầu.

**Prompt có thể dùng lại:**

> Triển khai script load và module refresh theo các quyết định trên. Đảm bảo payment join không nhân dòng, giữ surrogate key, kiểm tra ngày ngoài lịch, đóng kết nối mọi nhánh và chỉ xuất CSV sau khi database commit thành công.

## 4. Kiểm thử hành vi trước khi tạo minh chứng

AI bổ sung và điều chỉnh unit test cho các trường hợp:

- Refresh thành công: commit một lần, không rollback, đóng kết nối và xuất CSV đúng giá trị Decimal.
- SQL lỗi sau khi đã đo Before: rollback, không commit, đóng kết nối và giữ CSV thành công trước đó.
- Mart chưa tồn tại: trả bốn KPI bằng 0.
- Commit lỗi: rollback, đóng kết nối và không gọi bước xuất CSV.

AI chạy các test refresh, orchestration và checkpoint trước để phát hiện ảnh hưởng đến bước 7 và bước 8. Nhóm này đạt **31 tests**. Sau khi hoàn thiện, AI chạy toàn bộ bộ kiểm thử dự án, đạt **150 tests**.

Các test dùng kết nối giả lập kiểm tra nhánh lỗi; tính đúng của SQL và mức tăng dữ liệu được kiểm chứng riêng trên PostgreSQL thật ở bước tiếp theo.

## 5. Kiểm chứng với database thật và đối soát độc lập

AI kiểm tra kết nối PostgreSQL bằng truy vấn trực tiếp. Database đang cấu hình đã có **14.250 dòng Core order_items và 14.250 dòng fact**, nên chạy lại batch hiện có sẽ không thể hiện mức tăng mới.

AI tạo `scripts/demo_mart_reconciliation.py` để chuẩn bị phép đo có thể tái hiện:

1. Tạo database tạm có tên riêng theo UUID.
2. Tạo schema Core rồi sao chép dữ liệu từ database đang cấu hình.
3. Loại các đơn trong batch ngày 01/07/2026 và các dòng con tương ứng khỏi bản sao để tạo baseline.
4. Nạp Mart bằng SQL Buổi 4, sau đó chạy module mới để kiểm tra chuyển đổi schema cũ sang schema có `net_amount`.
5. Chuyển engine của loader và refresh sang database tạm; dùng thư mục tạm cho checkpoint và report.
6. Gọi `pipeline.main()` với các tham số CLI `--source file --input-dir ... --refresh-mart`, dùng ETL và PostgreSQL thật.
7. Truy vấn Core độc lập để tính KPI của các đơn thuộc batch và so sánh với từng diff trong CSV.
8. Kiểm tra lịch đủ ngày, không có fact trùng và `net_amount = revenue`.
9. Chạy lại cùng batch, xác nhận cả bốn diff bằng 0.
10. Lưu CSV của lần nạp gia tăng trước replay, lưu log và xóa database tạm trong `finally`.

Script cần quyền CREATEDB. Script giữ nguyên các bảng Core/Mart và checkpoint đang cấu hình; log ứng dụng vẫn ghi nhận các lần chạy kiểm chứng.

| KPI | Before | After | Diff đối soát với Core |
|---|---:|---:|---:|
| total_revenue | 61706432000.00 | 68932835500.00 | 7226403500.00 |
| order_count | 5000 | 5600 | 600 |
| completed_orders | 3880 | 4241 | 361 |
| total_items_sold | 16659 | 18578 | 1919 |

Cả bốn diff khớp Core; chạy lại cùng batch cho cả bốn diff bằng 0. Lịch có đủ 1.095 ngày, số fact trùng bằng 0 và số dòng lệch giữa `net_amount` với `revenue` bằng 0.

**Prompt có thể dùng lại:**

> Kiểm chứng trên PostgreSQL thật bằng database tạm. Nếu batch đã được nạp, tạo baseline trên bản sao thay vì xóa dữ liệu hiện có. Tính mức tăng kỳ vọng từ Core độc lập, đối chiếu bốn KPI, replay cùng batch và lưu minh chứng; luôn dọn database tạm.

## 6. Lệnh tái hiện và file bàn giao

Chạy tại thư mục gốc dự án trên PowerShell:

```powershell
# Kiểm thử module và điểm tích hợp
.\.venv\Scripts\python.exe -m pytest tests/test_refresh_mart.py tests/test_pipeline_orchestration.py tests/test_pipeline_checkpoint.py -q

# Tạo lại CSV và log minh chứng bằng database tạm
.\.venv\Scripts\python.exe -m scripts.demo_mart_reconciliation

# Kiểm tra toàn bộ dự án
.\.venv\Scripts\python.exe -m pytest -q
```

Để thực thi pipeline trên database đang cấu hình, lệnh dưới đây sẽ upsert Core, refresh Mart, xuất lại CSV và cập nhật checkpoint khi thành công:

```powershell
.\.venv\Scripts\python.exe -m src.pipeline --source file --input-dir data/incremental/day_2026-07-01 --refresh-mart
```

| Nội dung | File |
|---|---|
| Module refresh và KPI | [src/refresh_mart.py](../../src/refresh_mart.py) |
| SQL gia tăng | [12_load_data_mart.sql](../../sql/solutions/12_load_data_mart.sql) |
| Unit test refresh | [test_refresh_mart.py](../../tests/test_refresh_mart.py) |
| Script kiểm chứng thật | [demo_mart_reconciliation.py](../../scripts/demo_mart_reconciliation.py) |
| KPI Before/After | [kpi_comparison.csv](../kpi_comparison.csv) |
| Log minh chứng | [08-mart-refresh.txt](../evidence/08-mart-refresh.txt) |
| Hướng dẫn vận hành và quy ước | [08-mart-reconciliation.md](../08-mart-reconciliation.md) |

CSV được xuất sau commit database; hai thao tác này không thuộc cùng một transaction. Nếu ghi CSV thất bại sau commit, pipeline báo lỗi và không tiến checkpoint, nhưng Mart đã cập nhật. Chạy lại không sinh fact trùng; Before của lần chạy lại phản ánh Mart đã commit. Các bảng Core cũng có transaction riêng theo từng lần upsert, không nằm trong transaction refresh Mart.

Workflow này xác nhận nguồn file cho Bài 4, không bổ sung minh chứng mới cho nguồn API/both, cron hoặc recovery toàn pipeline.
