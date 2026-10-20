# Bài tập: TỰ ĐỘNG HÓA DAILY PIPELINE VÀ TÍCH HỢP END-TO-END

## Mục tiêu

- Tích hợp toàn diện các module từ Buổi 5 đến Buổi 7 thành một Data Pipeline tự động hóa hoàn chỉnh: **Trích xuất → Chuẩn hóa → Kiểm định → Nạp Database → Báo cáo Chất lượng → Làm mới Data Mart → Lưu Checkpoint**.
- Hỗ trợ thu thập dữ liệu từ nhiều nguồn khác nhau (File CSV/JSON, REST API, và mô hình kết hợp), kết hợp lưu trữ an toàn dữ liệu thô (RAW Immutability).
- Quản trị trạng thái tiến trình và điểm phục hồi (Checkpoint & Watermark), đảm bảo an toàn dữ liệu khi có sự cố và không sinh trùng lặp khi chạy lại (Idempotency).
- Tự động hóa làm mới Sales Data Mart và thực hiện đối soát biến động các chỉ số kinh doanh cốt lõi (KPI Reconciliation Before vs After).
- Tự động hóa thực thi định kỳ bằng Shell Script (`run_daily.sh`) và lập lịch tự động với Cron.
- Xây dựng cơ chế phát hiện sự cố, cảnh báo lỗi có cấu trúc và quy trình khôi phục an toàn (Failure Recovery).

## Bài 1: Điều phối Pipeline & Quản trị Lệnh Thực thi (Pipeline Orchestration & CLI Entrypoint)

- **File thực hiện:** `src/pipeline.py`

### Yêu cầu

1. Hỗ trợ giao diện dòng lệnh (CLI) bằng thư viện `argparse` với 4 tham số rõ ràng:
   - `--input-dir`: Đường dẫn thư mục chứa dữ liệu file theo ngày (mặc định: `data/incremental/day_2026-07-01`).
   - `--source`: Nguồn dữ liệu chỉ định, bắt buộc chọn một trong 3 giá trị `['file', 'api', 'both']` (mặc định: `file`).
   - `--refresh-mart`: Cờ kích hoạt làm mới Sales Data Mart sau khi nạp Core thành công (`action='store_true'`).
   - `--skip-processed-file`: Cờ bỏ qua thư mục batch file nếu đã từng được xử lý thành công trước đó (`action='store_true'`).
2. Điều phối quy trình xử lý khép kín tuần tự qua 8 bước và in log rõ ràng:
   1. **[1/8] Khởi tạo:** Sinh mã phiên chạy ngẫu nhiên `run_id` (dùng `uuid.uuid4()`), nạp thông tin từ file trạng thái `metadata/pipeline_state.json`.
   2. **[2/8] Trích xuất:** Đọc dữ liệu đầu vào theo cờ `--source` đã truyền (`_source_frames`).
   3. **[3/8] Chuẩn hóa & Schema:** Chuẩn hóa định dạng (`normalize`) và kiểm tra đủ các cột bắt buộc (`validate_schema`).
   4. **[4/8] Kiểm tra Chất lượng:** Áp dụng các bộ lọc (`split_valid_invalid`, `_split_duplicate_pk`, `split_cross_table_invalid`) để tách thành 2 luồng: hợp lệ (`valid`) và vi phạm (`reject`).
   5. **[5/8] Nạp Core Database:** Ghi các dòng vi phạm vào `data/rejected/<run_id>/<dataset>_reject.csv`. Nạp các dòng hợp lệ vào bảng PostgreSQL `core.<name>` bằng hàm `upsert_dataframe` có bọc transaction an toàn.
   6. **[6/8] Đối soát & Báo cáo:** Kiểm tra đẳng thức bất biến `input = valid + rejected` cho từng dataset (dùng `assert`, nếu sai lệch thì ném `AssertionError`). Sau đó tổng hợp báo cáo bằng `build_report()`.
   7. **[7/8] Làm mới Data Mart:** Nếu có truyền cờ `--refresh-mart`, gọi hàm `refresh_mart()`; nếu không truyền thì ghi nhận `SKIPPED`.
   8. **[8/8] Cập nhật Checkpoint:** Ghi đè trạng thái thành công mới vào file `metadata/pipeline_state.json` (chỉ ghi khi toàn bộ các bước trước đã thành công).
3. Ghi log đầy đủ vào `logs/pipeline.log` và màn hình terminal; ghi rõ `run_id`, dataset, số dòng `input`, `valid`, `reject`, `inserted`, `updated`.
4. Quản trị mã thoát hệ thống (Exit Code): Bọc hàm thực thi trong khối `try...except`. Khi hoàn thành trọn vẹn thì thoát với mã 0 (`sys.exit(0)`). Nếu có lỗi phát sinh ở bất kỳ bước nào thì ghi nhận `log.exception(...)` và thoát với mã 1 (`sys.exit(1)`).

### Kết quả cần đạt

Chạy lệnh `python -m src.pipeline --help` hiển thị đủ 4 tham số; khi chạy thành công, log thể hiện đủ tiến trình 8 bước và kết thúc với exit code 0. Khi gặp lỗi dừng ngay và trả về exit code 1.

### Minh chứng nộp

- Code: `src/pipeline.py`
- Output lệnh `--help`: `docs/evidence/08-help.txt` (Mẫu: hiển thị hướng dẫn sử dụng 4 flags).
- Log 1 lần chạy thành công: `docs/evidence/08-pipeline-log.txt` (Mẫu: `[1/8] Khởi tạo run_id=... | [5/8] orders input=600 valid=596 reject=4 inserted=596 updated=0 | [7/8] Làm mới Data Mart OK | [8/8] Cập nhật Checkpoint State OK | Pipeline hoàn thành (exit 0)`).

## Bài 2: Thu thập Dữ liệu Đa nguồn & Lưu trữ Dữ liệu Thô (Multi-Source Ingestion & RAW Capture)

- **File thực hiện:** `src/pipeline.py` (hàm `_source_frames`, `_file_frames`, `_api_frames`)

### Yêu cầu

1. Chế độ `--source file`: Đọc đủ 5 datasets từ thư mục `--input-dir` (`customers_daily.csv`, `products_daily.csv`, `orders_daily.csv`, `order_items_daily.csv`, `payments_daily.json`).
2. Chế độ `--source api`: Thu thập dữ liệu phân trang từ Mock REST API cho 5 endpoints (`/customers`, `/products`, `/orders`, `/order-items`, `/payments`) qua hàm `fetch_all_pages`, truyền mốc thời gian lọc `updated_after` lấy từ watermark trong file state; lưu trữ toàn bộ nội dung JSON thô nhận được vào `data/raw/<run_id>/<dataset>.json` trước khi chuyển sang DataFrame (bảo toàn dữ liệu gốc).
3. Chế độ kết hợp `--source both`: Áp dụng kiến trúc nạp lai thực tế:
   - Dữ liệu danh mục ít biến động (Master Data: `customers`, `products`): đọc từ file nội bộ trong thư mục `--input-dir`.
   - Dữ liệu giao dịch phát sinh liên tục (Transactional Data: `orders`, `order_items`, `payments`): thu thập từ REST API và lưu snapshot thô vào `data/raw/<run_id>/`.
4. Phân tách theo phiên chạy: Mỗi lần thực thi sinh một thư mục riêng theo `run_id` dưới `data/raw/` để lưu file thô, không ghi đè dữ liệu của các lần chạy trước đó.

### Kết quả cần đạt

Thực thi thành công cả 3 chế độ `--source file`, `--source api`, `--source both`; log ghi rõ nguồn dữ liệu; dữ liệu API lưu đúng cấu trúc thô tại `data/raw/<run_id>/`.

### Minh chứng nộp

- Log 3 chế độ nguồn: `docs/evidence/08-file.txt`, `docs/evidence/08-api.txt`, `docs/evidence/08-both.txt` (Mẫu: ghi rõ source, `run_id`, tên dataset và số dòng nạp).
- Cây thư mục RAW data: `docs/evidence/08-raw-tree.txt` (Mẫu: danh sách các file JSON trong `data/raw/<run_id>/`).

## Bài 3: Quản lý Trạng thái & Cơ chế Checkpoint (State & Checkpoint Management)

- **File thực hiện:** `src/pipeline.py` (hàm `_read_state`, `_write_state`, `run`), `metadata/pipeline_state.json`

### Yêu cầu

1. Cấu trúc file trạng thái `metadata/pipeline_state.json` lưu trữ các trường:
   - `last_run_id`: Mã phiên chạy thành công gần nhất.
   - `last_successful_at`: Thời gian hoàn tất theo chuẩn ISO 8601 UTC.
   - `last_source`: Nguồn dữ liệu của lần chạy thành công (`file`, `api`, hoặc `both`).
   - `status`: Trạng thái kết thúc (`success`).
   - `api_watermarks`: Dictionary lưu mốc thời gian lớn nhất (`updated_at` hoặc `created_at`) của các bản ghi API đã nạp thành công.
   - `processed_file_batches`: Danh sách đường dẫn thư mục file đã nạp thành công.
2. Nguyên tắc ghi nhận an toàn (Commit-on-Success): File state **chỉ** được ghi mới sau khi toàn bộ quy trình nạp Core, đối soát chất lượng và làm mới Data Mart hoàn tất thành công.
3. Bảo toàn trạng thái khi gặp lỗi: Nếu pipeline gặp sự cố ở bất kỳ bước nào, file state phải giữ nguyên giá trị cũ, tuyệt đối không cập nhật watermark mới khi dữ liệu chưa được commit vào database.
4. Cơ chế tiếp tục từ Checkpoint (Resume):
   - Với API: Lần chạy sau tự động đọc watermark từ state truyền vào `updated_after` để chỉ tải các bản ghi gia tăng mới hoặc có chỉnh sửa.
   - Với File: Khi bật cờ `--skip-processed-file`, nếu đường dẫn thư mục batch đã tồn tại trong `processed_file_batches` thì bỏ qua quá trình nạp.

### Kết quả cần đạt

Khi mô phỏng lỗi (tắt Database hoặc nhập sai đường dẫn file) → state giữ nguyên, pipeline trả exit code 1; sau khi sửa lỗi và chạy thành công → state cập nhật `run_id` và watermark mới.

### Minh chứng nộp

- File state thực tế: `metadata/pipeline_state.json`.
- Log kiểm chứng Checkpoint: `docs/evidence/08-checkpoint.txt` (Mẫu: ghi lại nội dung file state trước và sau lần chạy lỗi, và sau lần chạy thành công).

## Bài 4: Tích hợp Làm mới Data Mart & Đo lường KPI (Data Mart Integration & KPI Reconciliation)

- **File thực hiện:** `src/refresh_mart.py`, `docs/kpi_comparison.csv`, `docs/evidence/08-mart-refresh.txt`

### Yêu cầu

1. Hoàn thiện module `src/refresh_mart.py` thực thi kịch bản SQL `sql/solutions/12_load_data_mart.sql`:
   - Làm mới các bảng chiều (Dimension): `mart.dim_customer`, `mart.dim_product`, `mart.dim_payment_method`, `mart.dim_order_status`.
   - Tự động sinh bảng chiều thời gian `mart.dim_date` từ `2025-01-01` đến `2027-12-31` (`ON CONFLICT (date_key) DO NOTHING`).
   - Nạp bảng sự kiện `mart.fact_sales` từ `core.order_items` kết hợp `core.orders` và các bảng chiều, sử dụng cú pháp `ON CONFLICT (order_item_id) DO NOTHING`.
   - Quản lý kết nối an toàn: tự động `commit()` khi hoàn thành và `close()` kết nối trong khối `finally`.
2. Thực hiện truy vấn SQL đo lường 4 chỉ số KPI chính trên bảng `mart.fact_sales` trước và sau khi chạy batch gia tăng:
   - `total_revenue`: Tổng doanh thu thuần (`SUM(net_amount)`).
   - `order_count`: Tổng số đơn hàng (`COUNT(DISTINCT order_id)`).
   - `completed_orders`: Số đơn hàng có trạng thái hoàn thành (`completed`).
   - `total_items_sold`: Tổng số lượng sản phẩm bán ra (`SUM(quantity)`).
3. Xuất bảng đối chiếu KPI Before vs After ra file `docs/kpi_comparison.csv` theo định dạng chuẩn: `kpi,before,after,diff`.

### Kết quả cần đạt

Chạy cờ `--refresh-mart` thành công, bảng `mart.fact_sales` có dữ liệu mới; các chỉ số KPI sau khi nạp phản ánh chính xác lượng dữ liệu tăng thêm từ batch mới (cột `diff` tăng tương ứng).

### Minh chứng nộp

- Code: `src/refresh_mart.py`.
- Bảng đối chiếu KPI: `docs/kpi_comparison.csv` (Mẫu: `total_revenue,125400.00,131200.00,5800.00`).
- Log thực thi làm mới Mart: `docs/evidence/08-mart-refresh.txt` (Mẫu: log thực thi SQL refresh và kết quả truy vấn KPI).

## Bài 5: Tự động hóa Pipeline với Shell Script & Lập lịch Cron (Automation Script & Cron Scheduling)

- **File thực hiện:** `scripts/run_daily.sh`, `scripts/cron_example.txt`

### Yêu cầu

1. Xây dựng shell script `scripts/run_daily.sh`:
   - Khai báo `set -euo pipefail` ở đầu script để dừng ngay lập tức khi phát sinh lỗi hoặc biến chưa gán.
   - Tự động xác định đường dẫn thư mục gốc dự án theo vị trí script: `ROOT="$(cd "$(dirname "$0")/.." && pwd)"`.
   - Kích hoạt môi trường ảo Python (`.venv`).
   - Gọi lệnh thực thi pipeline: `python -m src.pipeline --source both --input-dir data/incremental/day_2026-07-01 --refresh-mart`.
   - Điều hướng toàn bộ kết quả chạy vào file log riêng theo ngày: `logs/pipeline_$(date +%Y%m%d).log`.
   - Trả về đúng mã kết thúc (exit code) của lệnh chạy Python.
   - Phân quyền thực thi cho script: `chmod +x scripts/run_daily.sh`.
2. Thiết lập cấu hình Cron trong `scripts/cron_example.txt`:
   - Khai báo biểu thức cron chạy tự động vào 02:00 sáng hàng ngày (`0 2 * * *`).
   - Sử dụng đường dẫn tuyệt đối cho script thực thi và log định kỳ.

### Kết quả cần đạt

Chạy lệnh `./scripts/run_daily.sh` tự động hoàn tất toàn bộ pipeline, tạo file log ngày `logs/pipeline_YYYYMMDD.log` và trả về exit code 0.

### Minh chứng nộp

- Script thực thi: `scripts/run_daily.sh`.
- File cấu hình Cron: `scripts/cron_example.txt`.
- Log chạy bằng script: `docs/evidence/08-daily.txt` (Mẫu: log chạy `./scripts/run_daily.sh` thành công kèm exit 0).

## Bài 6: Xử lý Sự cố & Khôi phục Pipeline (Pipeline Failure Recovery & Alerting)

- **File thực hiện:** `src/pipeline.py`, `docs/evidence/08-recovery.txt`

### Yêu cầu

1. Định dạng cảnh báo lỗi rõ ràng (Structured Alerting): Khi pipeline gặp lỗi ở bất kỳ bước nào (ví dụ: mất kết nối Database, API timeout hoặc sai cấu trúc dữ liệu), hệ thống phải ghi log cảnh báo với tiền tố `[ALERT]` hoặc `[CRITICAL]` chứa đầy đủ: mã phiên chạy (`run_id`), bước gặp lỗi (`step`), bảng dữ liệu (`dataset`), loại lỗi (`error_type`) và thông điệp lỗi ngắn gọn.
2. Bảo toàn trạng thái khi có lỗi: Khi xảy ra lỗi, pipeline phải dừng ngay lập tức, trả exit code 1, và giữ nguyên trạng thái trong `metadata/pipeline_state.json` (không cập nhật đè watermark khi dữ liệu chưa commit xong).
3. Thực hiện kịch bản kiểm thử khôi phục (Recovery Workflow):
   - **Lần 1 (Mô phỏng sự cố):** Cố ý tạo tình huống lỗi (ví dụ: ngắt kết nối PostgreSQL hoặc đặt sai mật khẩu DB) → ghi nhận log cảnh báo có nhãn `[ALERT]` và xác nhận file state không bị thay đổi.
   - **Khắc phục:** Bật lại dịch vụ PostgreSQL / hiệu chỉnh cấu hình kết nối đúng.
   - **Lần 2 (Chạy lại an toàn):** Chạy lại pipeline với cùng dữ liệu → pipeline đọc lại checkpoint cũ, nạp thành công toàn bộ dữ liệu vào Core và Data Mart mà không sinh bản ghi trùng lặp (Idempotent), sau đó cập nhật state mới.

### Kết quả cần đạt

Chứng minh được chuỗi xử lý sự cố hoàn chỉnh: Bắt lỗi rõ ràng → Báo động có cấu trúc → Bảo toàn trạng thái → Khắc phục sự cố → Chạy lại thành công không mất mát dữ liệu.

### Minh chứng nộp

- Log thực nghiệm phục hồi: `docs/evidence/08-recovery.txt` (Mẫu: log lần 1 báo lỗi kèm thẻ `[ALERT]`, nội dung state giữ nguyên, và log lần 2 chạy lại thành công kết thúc với exit 0).

## Danh mục nộp bài

| Bài tập | Minh chứng phải có | Đường dẫn file |
|---|---|---|
| Bài 1: Pipeline Orchestration | Code `pipeline.py` đủ 8 bước + log `--help` + log run thành công (exit 0) | `src/pipeline.py`<br>`docs/evidence/08-help.txt`<br>`docs/evidence/08-pipeline-log.txt` |
| Bài 2: Multi-Source Ingestion | Log 3 chế độ file, api, both + cây thư mục lưu trữ JSON thô | `docs/evidence/08-file.txt`<br>`docs/evidence/08-api.txt`<br>`docs/evidence/08-both.txt`<br>`docs/evidence/08-raw-tree.txt` |
| Bài 3: Checkpoint & State | File `pipeline_state.json` + log demo fail giữ state / success cập nhật state | `metadata/pipeline_state.json`<br>`docs/evidence/08-checkpoint.txt` |
| Bài 4: Data Mart Integration | Code `refresh_mart.py` + bảng KPI Before/After + log refresh | `src/refresh_mart.py`<br>`docs/kpi_comparison.csv`<br>`docs/evidence/08-mart-refresh.txt` |
| Bài 5: Automation & Scheduling | Script `run_daily.sh` (chmod +x) + file mẫu Cron + log chạy script | `scripts/run_daily.sh`<br>`scripts/cron_example.txt`<br>`docs/evidence/08-daily.txt` |
| Bài 6: Failure Recovery | Log kiểm thử khôi phục sự cố 2 lần chạy + Alert log `[ALERT]` | `docs/evidence/08-recovery.txt` |
