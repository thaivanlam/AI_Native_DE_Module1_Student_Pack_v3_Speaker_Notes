# Bài tập: XÂY DỰNG DATA INGESTION TỪ REST API

## Mục tiêu

- Khám phá và xây dựng tài liệu kỹ thuật cho hệ thống REST API nguồn (Endpoint, Authentication, Pagination, Filtering).
- Xây dựng HTTP Client hoàn chỉnh với cơ chế giới hạn thử lại (Bounded Retry), Exponential Backoff, quản trị Timeout và bảo mật Secret.
- Thu thập dữ liệu phân trang tự động, lưu trữ dữ liệu thô nguyên bản (RAW Immutability) trước khi xử lý.
- Nạp dữ liệu vào PostgreSQL thông qua kỹ thuật UPSERT (`ON CONFLICT DO UPDATE`), quản trị Transaction boundary và Connection Pool.
- Thiết lập quy trình kiểm thử tính bất biến (Idempotency Verification) nhằm ngăn ngừa nhân bản dữ liệu khi chạy lại pipeline.

---

## Bài 1: Khám phá REST API & Xây dựng Tài liệu Kỹ thuật (API Exploration & Documentation)

**File thực hiện:** `docs/api_docs.md`, `docs/evidence/06-explore-log.txt`

### Yêu cầu

1. **Kiểm tra Health check:** Gửi request `GET /health` đến Mock API (`http://localhost:8000`), kiểm tra phản hồi HTTP status `200` và body JSON `{"status": "ok"}`.
2. **Xác thực & Bảo mật (Authentication):**
   - Cấu hình secret qua biến môi trường `MOCK_API_KEY` (mặc định: `training-key`).
   - Gọi API kèm header `X-API-Key: training-key` → phản hồi `200 OK`.
   - Gọi API với key sai hoặc thiếu header → kiểm tra phản hồi lỗi `401 Unauthorized` kèm message `{"detail": "Invalid API key"}`.
   - Tuyệt đối không hard-code hoặc in lộ API key trong log và tài liệu (sử dụng mask `******`).
3. **Kiểm tra phân trang (Pagination):** Gửi request với tham số `page` (≥ 1) và `page_size` (1 − 500, mặc định: 100) (ví dụ `GET /orders?page=1&page_size=10`). Phân tích cấu trúc metadata trả về: `page`, `page_size`, `total`, `has_next`, `data`.
4. **Lọc dữ liệu gia tăng (Filtering):** Thử nghiệm tham số `updated_after` theo chuẩn ISO 8601 (ví dụ `?updated_after=2026-07-01T12:00:00Z`). Nếu sai định dạng ISO 8601 → kiểm tra mã lỗi `400 Bad Request` kèm message `{"detail": "updated_after must be ISO 8601"}`.
5. **Khảo sát 5 Endpoints nghiệp vụ:** Ghi nhận chính xác 5 resources: `/customers`, `/products`, `/orders`, `/order-items` (chú ý đường dẫn có dấu gạch ngang), `/payments`.

### Kết quả cần đạt

Tài liệu API hoàn chỉnh mô tả đủ 5 endpoints, tham số, mã lỗi (200, 400, 401); log gọi thử nghiệm che giấu API key đầy đủ.

### Minh chứng nộp

- **Tài liệu API:** `docs/api_docs.md` (Base URL, Headers, Endpoints, Params, Cấu trúc JSON, Mã lỗi).
- **Log kiểm thử:** `docs/evidence/06-explore-log.txt`

  Mẫu:
  ```
  GET /health -> 200 ok | sai key -> 401 Invalid API key | /orders?page=1&page_size=10 -> 10 rows has_next=true total=600
  ```

---

## Bài 2: Xây dựng HTTP Client với Bounded Retry & Exponential Backoff (HTTP Client Implementation)

**File thực hiện:** `src/api_client.py`

### Yêu cầu

1. **Cấu hình Timeout:** Thiết lập `timeout=10` cho mọi request `requests.get` nhằm ngăn ngừa hiện tượng treo tiến trình khi mạng chập chờn.
2. **Xác thực an toàn:** Đọc cấu hình `SETTINGS.api_url` và `SETTINGS.api_key` từ `src/config.py`, truyền qua header `X-API-Key`. Không ghi nhận secret thô vào log.
3. **Bắt lỗi HTTP & Raise Status:** Sử dụng `response.raise_for_status()` để phát hiện và ném ngoại lệ khi gặp HTTP status lỗi (4xx, 5xx), không trả về `None` âm thầm.
4. **Bounded Retry & Exponential Backoff:**
   - Giới hạn số lần thử lại: `max_retries=3`.
   - Thời gian chờ tăng theo cấp số nhân: `backoff_seconds * (2 ** (attempt - 1))` (lần 1: 1s, lần 2: 2s, lần 3: 4s).
   - Bắt các ngoại lệ mạng và lỗi parse JSON: `(requests.RequestException, ValueError)`.
   - Ghi log cảnh báo `log.warning(...)` kèm số lần thử (`attempt/max_retries`) và nguyên nhân lỗi.
   - Khi vượt quá số lần retry tối đa: Ném ngoại lệ `RuntimeError(f"API failed after {max_retries} attempts: {resource} page {page}")` kèm ngữ cảnh exception gốc (`from exc`).

### Kết quả cần đạt

Client tự động phục hồi khi gặp lỗi mạng tạm thời; retry tối đa 3 lần theo đúng chu kỳ backoff và ném lỗi rõ ràng nếu API không phản hồi; bảo mật hoàn toàn API key.

### Minh chứng nộp

- **Code:** `src/api_client.py`
- **Log demo retry:** `docs/evidence/06-retry-log.txt`

  Mẫu: dừng mock API → gọi client → ghi nhận 3 lần retry chờ 1s, 2s, 4s → ném `RuntimeError`; bật lại mock API → gọi thành công.

---

## Bài 3: Phân trang & Lưu trữ Dữ liệu Thô (Pagination & RAW Immutability)

**File thực hiện:** `src/api_client.py` (hàm `fetch_all_pages`), `src/pipeline.py`

### Yêu cầu

1. **Vòng lặp phân trang tự động:** Khởi tạo `page = 1`, duyệt liên tục gửi request lấy dữ liệu từng trang với tham số `page` và `page_size` (mặc định 100), truyền tham số `updated_after` nếu có.
2. **Điều kiện dừng chính xác:** Dừng vòng lặp khi `not payload.get('has_next')` (khi cờ `has_next` trả về `False`).
3. **Thu thập dữ liệu:** Nối các mảng bản ghi `payload.get('data', [])` của từng trang vào danh sách tổng hợp `rows`.
4. **Logging tiến độ:** Ghi log ở mức `INFO` sau mỗi trang: resource, page, số dòng trang hiện tại (`len(page_rows)`), tổng số dòng đã lấy (`total_so_far`).
5. **Bảo toàn dữ liệu gốc (RAW Capture):** Lưu trữ toàn bộ payload JSON nguyên bản vào file `data/raw/<run_id>/<resource>.json` (ví dụ `data/raw/<run_id>/orders.json`) trước khi thực hiện chuẩn hóa hoặc nạp database, tuân thủ nguyên tắc RAW Immutability.

### Kết quả cần đạt

Thu thập đầy đủ 100% bản ghi của tài nguyên không sót trang (ví dụ đủ 600 orders với 6 trang); lưu file JSON thô chuẩn xác tại thư mục RAW theo từng `run_id`.

### Minh chứng nộp

- **Code:** `src/api_client.py`
- **File RAW thật (ít nhất 1 run):** `data/raw/<run_id>/orders.json`
- **Log phân trang:** `docs/evidence/06-fetch-log.txt`

  Mẫu:
  ```
  resource=orders page=1 rows=100 ... page=6 rows=100 total_so_far=600 | RAW saved to data/raw/<run_id>/orders.json
  ```

---

## Bài 4: Nạp Dữ liệu vào PostgreSQL với Kỹ thuật UPSERT (Database Upsert & Transactions)

**File thực hiện:** `src/load_postgres.py` (hàm `upsert_dataframe(name: str, df: pd.DataFrame) -> dict`)

### Yêu cầu

1. **Ánh xạ Khóa chính (Primary Key Mapping):** Khai báo từ điển `PK` định danh khóa chính khớp 100% với schema `core` trong database:

   | Bảng | Khóa chính |
   |---|---|
   | `customers` | `customer_id` |
   | `products` | `product_id` |
   | `orders` | `order_id` |
   | `order_items` | `order_item_id` |
   | `payments` | `payment_id` |

2. **Xây dựng câu lệnh PostgreSQL UPSERT:** Sử dụng cú pháp:

   ```sql
   INSERT INTO core.{name} ({cols}) VALUES ({placeholders})
   ON CONFLICT ({pk}) DO UPDATE SET {updates}
   ```

   - Tự động sinh danh sách cột cập nhật: `{col} = EXCLUDED.{col}` cho toàn bộ các cột ngoại trừ khóa chính `{pk}` và cột kỹ thuật `error_code` (nếu có).
   - Bảng đích bắt buộc thuộc schema `core` (`core.<name>`).
3. **Quản trị Transaction & Connection Pool:** Sử dụng SQLAlchemy engine kết hợp context manager `with engine.begin() as conn:` để đảm bảo transaction ACID (tự động commit khi hoàn tất, tự động rollback nếu gặp lỗi giữa chừng). Không mở connection riêng lẻ cho từng dòng.
4. **Ép kiểu an toàn (Data Sanitization):** Xử lý các giá trị `NaN`, `NaT`, `<NA>` của pandas thành `None` (tương ứng `NULL` trong PostgreSQL) trước khi bind params vào câu SQL.
5. **Thống kê Insert & Update:** So sánh tập khóa chính đầu vào (`incoming_ids`) với tập khóa chính đã tồn tại trong database (`existing_ids`) để đo lường chính xác:
   - `inserted = len(incoming_ids - existing_ids)`
   - `updated = len(incoming_ids & existing_ids)`
   - Trả về dictionary: `{'inserted': inserted, 'updated': updated, 'inserted_or_updated': len(records)}`.

### Kết quả cần đạt

Dữ liệu nạp thành công vào schema `core`; transaction rollback an toàn nếu vi phạm ràng buộc; phân tách chính xác số lượng inserted vs updated.

### Minh chứng nộp

- **Code:** `src/load_postgres.py`
- **Log thực thi upsert:** `docs/evidence/06-upsert-log.txt`

  Mẫu:
  ```
  [UPSERT] table=core.orders incoming=600 inserted=600 updated=0 | Verification: SELECT COUNT(*) FROM core.orders = 600
  ```

---

## Bài 5: Kiểm thử Tính Bất biến & Chống Trùng lặp (Idempotency Testing & Verification)

**File thực hiện:** `docs/idempotency_test.md`

### Yêu cầu

1. **Kịch bản kiểm thử:** Thực hiện nạp cùng một tập dữ liệu API (ví dụ 600 orders) vào PostgreSQL liên tiếp 2 lần (Run 1 và Run 2).
2. **Thu thập số liệu nghiệm thu:**
   - **Lần 1 (Cold Start):** Ghi nhận số dòng `inserted`, `updated`, và `SELECT COUNT(*)` sau nạp.
   - **Lần 2 (Re-run cùng dữ liệu):** Ghi nhận số dòng `inserted` (phải bằng 0), `updated` (bằng tổng số bản ghi), và `SELECT COUNT(*)`.
3. **Đối soát tính toàn vẹn (Integrity Verification):** Thực hiện truy vấn SQL kiểm tra:

   ```sql
   SELECT COUNT(*) FROM core.orders;
   SELECT COUNT(DISTINCT order_id) FROM core.orders;
   ```

   Xác nhận tổng số dòng và số khóa chính duy nhất bằng nhau và giữ nguyên giữa 2 lần chạy.
4. **Báo cáo kết quả:** Trình bày chi tiết bảng so sánh Run 1 vs Run 2 và kết luận rõ ràng đạt/không đạt.

### Kết quả cần đạt

Chạy lại pipeline nhiều lần với cùng dữ liệu không làm tăng số dòng và không sinh bản ghi trùng lặp trong PostgreSQL (`COUNT(*)` không đổi, `inserted = 0`, toàn bộ chuyển thành `updated`).

### Minh chứng nộp

- **Báo cáo kiểm thử Idempotency:** `docs/idempotency_test.md` (chứa câu lệnh thực hiện, bảng số liệu 2 lần chạy, câu lệnh SQL verify và kết luận).

---

## Danh mục nộp bài

| Bài tập | Minh chứng phải có | Đường dẫn file |
|---|---|---|
| Bài 1: API Exploration | Tài liệu API chuẩn hóa + Log kiểm thử 4 kịch bản (che key) | `docs/api_docs.md`<br>`docs/evidence/06-explore-log.txt` |
| Bài 2: HTTP Client | Code `fetch_all_pages` có retry/backoff/timeout + Log mô phỏng retry | `src/api_client.py`<br>`docs/evidence/06-retry-log.txt` |
| Bài 3: Pagination & RAW | Code phân trang + File RAW thật + Log tổng kết thu thập dữ liệu | `src/api_client.py`<br>`data/raw/<run_id>/orders.json`<br>`docs/evidence/06-fetch-log.txt` |
| Bài 4: Database Upsert | Code `upsert_dataframe` (`core.*`, transaction) + Log kiểm tra inserted/updated | `src/load_postgres.py`<br>`docs/evidence/06-upsert-log.txt` |
| Bài 5: Idempotency Test | Báo cáo kiểm thử 2 lần chạy + Bảng số liệu đối soát + SQL verify | `docs/idempotency_test.md` |
