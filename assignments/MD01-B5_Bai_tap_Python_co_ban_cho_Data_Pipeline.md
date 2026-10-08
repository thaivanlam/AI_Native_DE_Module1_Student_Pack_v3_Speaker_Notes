# Bài tập: PYTHON CƠ BẢN CHO DATA PIPELINE

## Mục tiêu

- Thiết lập môi trường ảo (`.venv`) và cấu trúc dự án chuẩn modular (`src/config.py`, `src/logger.py`, `src/extract_files.py`, `src/transform.py`).
- Xây dựng tầng trích xuất dữ liệu đa định dạng (CSV, JSON) và hồ sơ hóa kỹ thuật (Technical Profiling).
- Thực hiện chuẩn hóa kỹ thuật (Data Normalization) trước khi đưa vào vùng STAGING, bảo toàn tuyệt đối dữ liệu gốc (RAW Immutability).
- Xây dựng hệ thống logging 2 kênh (Console & File) và xử lý ngoại lệ có chủ đích (Targeted Exception Handling).

---

## Phần 1: Bắt buộc

### 1.1 Khởi tạo Môi trường & Quản trị Cấu hình (Environment & Config)

- **File thực hiện:** `src/config.py`, `.env.example`
- **Yêu cầu:**
  1. Khởi tạo virtual environment: `python -m venv .venv`, kích hoạt môi trường và cài đặt dependencies từ `requirements.txt`.
  2. Tạo template `.env.example` chứa các biến môi trường chuẩn: `DATABASE_URL`, `MOCK_API_URL`, `MOCK_API_KEY`. Tuyệt đối không commit file `.env` thật lên Git.
  3. Hoàn thiện dataclass `Settings` (`frozen=True`) trong `src/config.py`:
     - Đọc cấu hình từ môi trường thông qua `python-dotenv` và `os.getenv`.
     - Tự động xác định đường dẫn gốc `root = Path(__file__).resolve().parents[1]`.
     - Định nghĩa các đường dẫn thư mục chuẩn dạng `Path`: `raw_dir`, `staging_dir`, `reject_dir`, `metadata_dir`, `report_dir`.
     - Khởi tạo đối tượng toàn cục `SETTINGS = Settings()`.
- **Kết quả cần đạt:** Cài đặt package thành công (pandas, sqlalchemy, psycopg); `from src.config import SETTINGS` hoạt động mượt mà; các thuộc tính đường dẫn trả về đúng kiểu `Path`.
- **Minh chứng nộp:**
  - Code: `src/config.py` và template `.env.example`.
  - Log tạo venv & kiểm tra package: `docs/evidence/05-env-setup.txt` (Mẫu: `Python 3.11... pip list shows pandas, sqlalchemy, psycopg...`).
  - Log in cấu hình SETTINGS: `docs/evidence/05-config.txt` (Mẫu: `SETTINGS(root=..., database_url=..., raw_dir=...)`).

### 1.2 File Ingestion & Trích xuất Dữ liệu (CSV & JSON)

- **File thực hiện:** `src/extract_files.py` (hàm `read_dataset(path: Path) -> pd.DataFrame`)
- **Yêu cầu:**
  1. Quản lý đường dẫn bằng `pathlib.Path`. Kiểm tra file tồn tại; nếu không tồn tại → `raise FileNotFoundError(f"Missing file: {path}")`.
  2. Định dạng CSV (`.csv`): Đọc bằng `pd.read_csv(path)` với mã hóa `utf-8` (xử lý dự phòng `utf-8-sig` nếu phát hiện ký tự BOM).
  3. Định dạng JSON (`.json`): Đọc qua `json.loads(path.read_text(encoding='utf-8'))`. Hỗ trợ cả 2 dạng cấu trúc: danh sách object `[ {...}, ... ]` hoặc object bọc danh sách `{"data": [ ... ]}` → chuyển đổi thành DataFrame.
  4. Nếu phần mở rộng file không được hỗ trợ (khác `.csv`, `.json`), `raise ValueError(f"Unsupported file: {path}")`.
  5. Kiểm tra file rỗng: Nếu DataFrame sau khi đọc có `len(df) == 0` → `raise ValueError(f"Empty dataset: {path}")`.
- **Kết quả cần đạt:** Đọc thành công toàn bộ 5 dataset của batch `data/incremental/day_2026-07-01/` (`customers_daily.csv`, `products_daily.csv`, `orders_daily.csv`, `order_items_daily.csv`, `payments_daily.json`) thành DataFrame; bắt lỗi chính xác khi file không tồn tại hoặc sai định dạng.
- **Minh chứng nộp:**
  - Code: `src/extract_files.py`
  - Log trích xuất thành công và log bắt lỗi file: `docs/evidence/05-extract.txt` (Mẫu: `[SUCCESS] customers_daily.csv: 100 rows | payments_daily.json: 536 rows | [ERROR] missing.csv -> FileNotFoundError`).

### 1.3 Data Profiling Kỹ thuật (Profiling Baseline)

- **File thực hiện:** `src/extract_files.py` (hàm `profile(df: pd.DataFrame) -> dict`)
- **Yêu cầu:**
  1. Thống kê số lượng: Tổng số dòng (`rows: len(df)`), danh sách tên cột (`columns: list(df.columns)`).
  2. Thống kê độ đầy đủ (Completeness): Đếm số lượng giá trị thiếu/NULL theo từng cột (`missing: df.isna().sum().to_dict()`).
  3. Thống kê tính duy nhất (Uniqueness): Đếm số dòng trùng lặp toàn bộ bản ghi (`duplicates: int(df.duplicated().sum())`).
  4. Trả về cấu trúc dictionary chuẩn: `{'rows': int, 'columns': list, 'missing': dict, 'duplicates': int}`
- **Kết quả cần đạt:** Hàm chạy chính xác cho cả 5 dataset từ `data/incremental/day_2026-07-01/`; số liệu thống kê chuẩn xác, không crash khi gặp kiểu dữ liệu hỗn hợp.
- **Minh chứng nộp:**
  - Code: `src/extract_files.py`
  - Báo cáo profiling 5 dataset: `docs/evidence/05-profiling.txt` (Mẫu: `dataset=customers_daily rows=100 cols=10 missing={...} duplicates=0`).

### 1.4 Technical Data Normalization (Chuẩn hóa Kỹ thuật)

- **File thực hiện:** `src/transform.py` (hàm `normalize(df: pd.DataFrame) -> pd.DataFrame`)
- **Yêu cầu:** Tuân thủ nguyên tắc không biến đổi dữ liệu nguồn (RAW Immutability):
  1. **Bảo toàn RAW:** Khởi tạo bản sao độc lập bằng `out = df.copy()`, tuyệt đối không thay đổi DataFrame đầu vào.
  2. **Chuẩn hóa tên cột:** Cắt tỉa khoảng trắng đầu/cuối và lowercase toàn bộ: `out.columns = [c.strip().lower() for c in out.columns]`.
  3. **Chuẩn hóa chuỗi (Strings):** Duyệt qua các cột kiểu `object`, áp dụng `strip()` loại bỏ khoảng trắng thừa đầu cuối.
  4. **Chuẩn hóa Email & Enums** (khớp 100% ràng buộc Database):
     - Cột `email`: Chuyển về chữ thường (`.str.lower()`).
     - Các cột phân loại (`status`, `payment_status`, `payment_method`, `channel`): Chuyển về chữ thường (`.str.lower()`) để khớp với các ràng buộc CHECK của Postgres (`active`, `inactive`, `discontinued`, `pending`, `confirmed`, `shipped`, `completed`, `cancelled`, `web`, `mobile_app`, `social`, `cash`, `bank_transfer`, `card`, `e_wallet`, `success`, `failed`, `refunded`).
  5. **Ép kiểu số (Numerics):** Ép kiểu các cột số (`unit_price`, `cost_price`, `order_total`, `discount_amount`, `amount`, `quantity`) bằng `pd.to_numeric(out[col], errors='coerce')` (giá trị lỗi parse chuyển thành `NaN`).
  6. **Ép kiểu thời gian (Timestamps):** Tự động phát hiện các cột có hậu tố `_at` hoặc `_date` (như `order_date`, `payment_date`, `created_at`, `updated_at`), ép kiểu bằng `pd.to_datetime(out[col], errors='coerce', utc=True)`.
- **Kết quả cần đạt:** Dữ liệu đầu ra sạch về mặt kỹ thuật; loại bỏ triệt để khoảng trắng thừa; email và enums đồng nhất chữ thường; kiểu số và ngày tháng chuẩn hóa UTC; DataFrame gốc không bị mutate.
- **Minh chứng nộp:**
  - Code: `src/transform.py`
  - Bảng so sánh Before vs After 5 dòng mẫu: `docs/evidence/05-normalize.txt` (Mẫu: so sánh chi tiết tên cột, string, email, enum, datetime, numeric).

### 1.5 Pipeline Logging & Xử lý Ngoại lệ (Logging & Exception Handling)

- **File thực hiện:** `src/logger.py` (hàm `get_logger(name: str = 'pipeline')`)
- **Yêu cầu:**
  1. Tự động kiểm tra và tạo thư mục `logs/` nếu chưa tồn tại (`Path('logs').mkdir(exist_ok=True)`).
  2. Cấu hình đồng thời 2 handlers:
     - **File Handler:** Ghi vào `logs/pipeline.log` với mã hóa `encoding='utf-8'`.
     - **Stream Handler:** Xuất ra màn hình console/terminal.
  3. Tránh duplicate handlers khi gọi nhiều lần: `if logger.handlers: return logger`.
  4. Cấu hình log level tối thiểu `INFO`, định dạng thống nhất: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`
  5. **Xử lý ngoại lệ có chủ đích:** Bắt các exception cụ thể (`FileNotFoundError`, `ValueError`), ghi log ở mức `ERROR` kèm ngữ cảnh rõ ràng (dataset name, file path) trước khi raise. Tuyệt đối không dùng bare `except:`.
- **Kết quả cần đạt:** Thông điệp log xuất hiện đồng thời trên console và lưu trữ trong `logs/pipeline.log`; log rõ ràng các mốc xử lý file và ghi nhận chính xác trường hợp gặp lỗi.
- **Minh chứng nộp:**
  - Code: `src/logger.py`
  - File log mẫu chứa log hoạt động và 1 trường hợp lỗi: `docs/evidence/05-logging.txt` (hoặc trích đoạn từ `logs/pipeline.log`).

---

## Phần 2: Nâng cao

### 2.1 File Ingestion Batch Runner (RAW → STAGING Pipeline)

- **File thực hiện:** `scripts/run_file_pipeline.py`
- **Yêu cầu:**
  1. Xây dựng script batch runner hoàn chỉnh, nhận tham số `--input-dir` (mặc định: `data/incremental/day_2026-07-01`).
  2. Tích hợp toàn bộ module đã xây dựng: đọc config từ `SETTINGS`, khởi tạo logger qua `get_logger()`.
  3. Duyệt tuần tự 5 dataset (`customers`, `products`, `orders`, `order_items`, `payments`), thực hiện chuỗi: `read_dataset` → `profile` → `normalize`.
  4. Xuất dữ liệu đã chuẩn hóa vào vùng STAGING: `data/staging/<dataset>_clean.csv`.
  5. Bảo toàn dữ liệu gốc: Xác nhận file trong thư mục đầu vào giữ nguyên 100%.
- **Kết quả cần đạt:** Chạy lệnh `python scripts/run_file_pipeline.py` hoàn tất trơn tru; sinh đủ 5 file clean trong `data/staging/`; log ghi nhận chi tiết row count input và output.
- **Minh chứng nộp:**
  - Script: `scripts/run_file_pipeline.py`
  - Cây thư mục `data/staging/` và log chạy pipeline: `docs/evidence/05-staging-runner.txt`.

### 2.2 Automated Test Suite (Pytest Unit Tests)

- **File thực hiện:** `tests/test_extract.py`, `tests/test_transform.py`
- **Yêu cầu:** Viết bộ test tự động với pytest bao phủ tối thiểu 8 ca kiểm thử:
  1. `test_read_csv_success`: Đọc file CSV trả về DataFrame hợp lệ.
  2. `test_read_json_nested_data`: Đọc JSON cấu trúc list hoặc bọc bởi `{"data": [...]}`.
  3. `test_read_file_not_found`: Kiểm tra ném `FileNotFoundError` khi đường dẫn file không tồn tại.
  4. `test_unsupported_file_extension`: Kiểm tra ném `ValueError` với định dạng không hỗ trợ.
  5. `test_profile_metrics`: Đo lường chính xác rows, columns, missing, duplicates.
  6. `test_normalize_raw_immutability`: Xác nhận DataFrame nguồn không bị thay đổi sau khi chuẩn hóa.
  7. `test_normalize_strings_and_enums`: Xác nhận trim khoảng trắng và lowercase `email`, `status`, `payment_method`, `channel`.
  8. `test_normalize_numeric_and_datetime`: Xác nhận ép kiểu số và parse ISO/UTC datetime.
- **Kết quả cần đạt:** Chạy lệnh `pytest tests/test_extract.py tests/test_transform.py -v` đạt 100% pass (tối thiểu 8 passed).
- **Minh chứng nộp:**
  - File test: `tests/test_extract.py`, `tests/test_transform.py`
  - Log thực thi pytest: `docs/evidence/05-pytest.txt`.

---

## Danh mục nộp bài & Rubric

| Task | Minh chứng phải có | Đường dẫn file |
|---|---|---|
| 1.1 Environment & Config | Code Settings + Template `.env.example` + Log venv & pip list | `src/config.py`<br>`.env.example`<br>`docs/evidence/05-env-setup.txt`<br>`docs/evidence/05-config.txt` |
| 1.2 File Extraction | Code `read_dataset` + Log đọc CSV/JSON và demo bắt lỗi file thiếu | `src/extract_files.py`<br>`docs/evidence/05-extract.txt` |
| 1.3 Data Profiling | Code `profile` + Báo cáo profiling mẫu cho 5 datasets | `src/extract_files.py`<br>`docs/evidence/05-profiling.txt` |
| 1.4 Normalization | Code `normalize` + Bảng so sánh 5 dòng Before vs After | `src/transform.py`<br>`docs/evidence/05-normalize.txt` |
| 1.5 Logging & Exception | Code `get_logger` + File log pipeline (đủ 2 handlers, INFO + 1 ERROR) | `src/logger.py`<br>`docs/evidence/05-logging.txt`<br>`logs/pipeline.log` |
| Bonus 2.1 Staging Runner | Script runner + Cây thư mục `data/staging/` + Log pipeline run | `scripts/run_file_pipeline.py`<br>`docs/evidence/05-staging-runner.txt` |
| Bonus 2.2 Pytest Suite | File test unit tests + Log pytest pass 100% (≥8 tests) | `tests/test_extract.py`<br>`tests/test_transform.py`<br>`docs/evidence/05-pytest.txt` |
