# AI-Native Data Engineering – Module 1 – Student Pack

Bộ tài liệu thực hành 8 buổi của Module 1, xoay quanh một bài toán xuyên suốt: xây dựng hệ thống dữ liệu cho một **E-commerce**, từ yêu cầu nghiệp vụ tới một **daily pipeline tự động**.

```
Business Requirement → ERD → PostgreSQL OLTP → SQL Analytics → Sales Data Mart
→ Python File/API Ingestion → Data Quality → Automated Daily Pipeline
```

> **Bản không chứa đáp án.** Giảng viên có thể phát material theo lịch từng buổi để giữ nhịp challenge/quiz.
> Đây là bản **Speaker Notes edition**: slide `.pptx` có ghi chú giảng dạy ở Notes pane (xem [SPEAKER_NOTES_EDITION.md](SPEAKER_NOTES_EDITION.md)).

---

## Mục lục
1. [Nguyên tắc xuyên suốt](#1-nguyên-tắc-xuyên-suốt)
2. [Yêu cầu môi trường](#2-yêu-cầu-môi-trường)
3. [Quick start](#3-quick-start)
4. [Lộ trình 8 buổi](#4-lộ-trình-8-buổi)
5. [Cấu trúc thư mục](#5-cấu-trúc-thư-mục)
6. [Dữ liệu](#6-dữ-liệu)
7. [Database & SQL](#7-database--sql)
8. [Python pipeline](#8-python-pipeline)
9. [Mock REST API](#9-mock-rest-api)
10. [Scripts tiện ích](#10-scripts-tiện-ích)
11. [Nộp bài & evidence](#11-nộp-bài--evidence)
12. [Troubleshooting](#12-troubleshooting)
13. [Không có trong pack này](#13-không-có-trong-pack-này)

---

## 1. Nguyên tắc xuyên suốt
- **Không sửa RAW.** File nguồn trong `data/` và dữ liệu đã lưu vào `data/raw/` là bất biến; mọi làm sạch diễn ra ở bước transform.
- **Tái chạy được (idempotent / rerun-safe).** Script SQL và pipeline chạy lại nhiều lần phải cho cùng kết quả, không nhân đôi dữ liệu.
- **Đối soát được.** Row count, reject count, DQ report phải khớp và có evidence.
- **Không hard-code secret.** Mọi thông số kết nối đọc từ `.env`.

## 2. Yêu cầu môi trường

| Công cụ | Phiên bản | Ghi chú |
|---|---|---|
| Docker Desktop | mới nhất | chạy PostgreSQL 16 và Mock API |
| Python | 3.11 | dùng từ Buổi 5 |
| Git | bất kỳ | commit evidence sau mỗi buổi |
| DBeaver (khuyến nghị) | Community | xem ERD, chạy query |
| VS Code (khuyến nghị) | — | |

Hướng dẫn cài trên macOS: [scripts/setup_macos.md](scripts/setup_macos.md) và `./scripts/preflight_macos.sh`.
Trên Windows: dùng **Git Bash** hoặc **WSL** để chạy các script `.sh`.

Thông số mặc định trong [.env.example](.env.example):

| Biến | Giá trị |
|---|---|
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `ecommerce` / `de_user` / `de_password` |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5432` |
| `DATABASE_URL` | `postgresql+psycopg://de_user:de_password@localhost:5432/ecommerce` |
| `MOCK_API_URL` / `MOCK_API_KEY` | `http://localhost:8000` / `training-key` |

## 3. Quick start

```bash
# 1. Cấu hình môi trường
cp .env.example .env

# 2. Khởi động PostgreSQL (container: ecommerce-postgres)
docker compose up -d postgres
docker compose ps                 # chờ trạng thái "healthy"

# 3. Sau khi hoàn thiện sql/student/01_create_oltp.sql (Buổi 1):
./scripts/bootstrap.sh            # reset schema core/mart, tạo bảng, nạp seed data

# 4. Từ Buổi 5: môi trường Python
python3.11 -m venv .venv
source .venv/bin/activate         # Windows (Git Bash): source .venv/Scripts/activate
pip install -r requirements.txt
[ -d src ] || cp -R starter/src src   # chỉ chạy MỘT lần

# 5. Từ Buổi 6: Mock API (container: ecommerce-mock-api)
docker compose up -d mock-api
curl http://localhost:8000/health
```

## 4. Lộ trình 8 buổi

Mỗi buổi 90 phút lab, gồm slide (`slides/`), lab (`labs/`), bài tập (`assignments/`) và quiz (`quizzes/`).

| Buổi | Chủ đề | Output chính | Dữ liệu |
|---|---|---|---|
| 1 | Tổng quan hệ thống dữ liệu & thiết kế E-commerce Database | ERD (`database/ecommerce_oltp.dbml`), `sql/student/01_create_oltp.sql` | — |
| 2 | SQL thực chiến cho Business Analytics | `02_exercises_basic.sql`, EXPLAIN | `data/seed/` |
| 3 | SQL nâng cao cho KPI & Customer Analytics (CTE, Window, Cohort) | `03_*.sql` | `data/seed/` |
| 4 | Thiết kế Sales Data Mart | `04_data_mart.sql` (schema `mart`) | `data/seed/` |
| 5 | Python cơ bản cho Data Pipeline | `src/extract_files.py`, `transform.py`, `logger.py` | `data/incremental/` |
| 6 | Data Ingestion từ REST API | `src/api_client.py` (pagination, retry, RAW capture, upsert) | Mock API |
| 7 | Data Cleaning & Data Quality | `src/validators/`, reject/quarantine, DQ report | `data/dirty/` |
| 8 | Tự động hóa Daily Pipeline & End-to-End | `src/pipeline.py`, checkpoint, `run_daily.sh`, cron | `data/incremental/` + API |

Tổng kết: [assignments/mini_project.md](assignments/mini_project.md) – *Automated E-commerce Data Ingestion Pipeline*.

## 5. Cấu trúc thư mục

```
.
├── slides/            # 8 slide deck (.pptx, có Speaker Notes)
├── labs/              # session_01.md … session_08.md – hướng dẫn thực hành
├── assignments/       # bài tập sau buổi + mini_project.md
├── quizzes/           # quiz từng buổi (.csv, không có đáp án)
├── docs/              # requirement, data contract, data dictionary, Lab Manual, evidence
│   ├── business_requirements.md
│   ├── data_contract.md
│   ├── data_dictionary.csv
│   ├── dataset_summary.json
│   ├── Course_Overview_Student.md
│   ├── Student_Lab_Manual_Module1_8_Buoi.docx
│   ├── evidence/          # ảnh/log minh chứng theo buổi (01-*, 02-*, 03-*)
│   └── explain_output/    # kết quả EXPLAIN / phân tích hiệu năng
├── database/          # ERD của học viên (ecommerce_oltp.dbml)
├── sql/
│   ├── README.md          # hướng dẫn chạy chi tiết
│   └── student/           # nơi viết SQL Buổi 1–4
├── data/
│   ├── seed/              # baseline database cho Buổi 2–4
│   ├── incremental/day_2026-07-01/   # daily batch SẠCH cho Buổi 5, 6, 8
│   ├── dirty/day_2026-07-02/         # batch BẨN cho Buổi 7 (không sửa trực tiếp)
│   ├── raw/               # (runtime) RAW capture do pipeline sinh ra
│   └── reject/            # (runtime) bản ghi bị quarantine
├── starter/src/       # Python skeleton – copy sang src/ ở đầu Buổi 5
├── mock_api/          # FastAPI giả lập nguồn REST cho Buổi 6–8
├── tests/             # public Data Quality tests (pytest)
├── scripts/           # bootstrap/reset/run_daily/cron & setup
├── metadata/          # (runtime) checkpoint / watermark
├── reports/           # (runtime) DQ report
├── logs/              # (runtime) log pipeline
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

> `metadata/`, `reports/`, `logs/`, `data/raw/`, `data/reject/` là **output/runtime artifacts** – không phải lời giải hay dataset gốc. Nội dung các thư mục này được `.gitignore` bỏ qua (chỉ giữ `.gitkeep`).

## 6. Dữ liệu

7 thực thể: `categories`, `customers`, `products`, `order_status`, `orders`, `order_items`, `payments`. Định nghĩa cột xem [docs/data_dictionary.csv](docs/data_dictionary.csv), quy ước dữ liệu xem [docs/data_contract.md](docs/data_contract.md).

| Dataset | Seed (`data/seed/`) | Incremental 2026-07-01 |
|---|---:|---:|
| customers | 1,000 | 100 |
| products | 500 | 50 |
| orders | 5,000 | 600 |
| order_items | 12,717 | 1,533 |
| payments | 4,517 | 536 |

- **Seed**: CSV, dùng để nạp baseline cho CORE (Buổi 2–4).
- **Incremental / Dirty**: 4 file CSV + `payments_daily.json`, mô phỏng batch hàng ngày.
- **Dirty batch** chứa lỗi cố ý (schema, business rule, integrity, duplicate…). Nhiệm vụ là phát hiện và tách ra `data/reject/`, **không** sửa file nguồn.

## 7. Database & SQL

- Schema `core`: OLTP (7 bảng, FK, index, CHECK/DEFAULT).
- Schema `mart`: Sales Data Mart (Buổi 4).

| File | Nội dung |
|---|---|
| `sql/student/01_create_oltp.sql` | DDL tạo schema `core` |
| `sql/student/tests/01_bonus_constraint_tests.sql` | test CHECK/DEFAULT (chạy trong transaction, ROLLBACK) |
| `sql/student/02_exercises_basic.sql` | truy vấn cơ bản: filter, aggregate, JOIN |
| `sql/student/03_exercises_advanced.sql` | truy vấn nâng cao cho KPI |
| `sql/student/03_cte_window_cohort.sql` | CTE, window function, cohort/retention |
| `sql/student/04_data_mart.sql` | Sales Data Mart |
| `sql/student/05_performance_index.sql` | index & tối ưu hiệu năng |

Chạy một file SQL:

```bash
# Bash / Git Bash
docker exec -i ecommerce-postgres psql -U de_user -d ecommerce -v ON_ERROR_STOP=1 < sql/student/02_exercises_basic.sql
```

```powershell
# PowerShell (không hỗ trợ redirect "<")
Get-Content sql/student/02_exercises_basic.sql -Raw | docker exec -i ecommerce-postgres psql -U de_user -d ecommerce -v ON_ERROR_STOP=1
```

Mở psql tương tác: `docker exec -it ecommerce-postgres psql -U de_user -d ecommerce`.

Hướng dẫn đầy đủ (thứ tự chạy, câu verify, quan hệ bảng): [sql/README.md](sql/README.md).

## 8. Python pipeline

Làm việc trong `src/` (copy từ `starter/src/` ở đầu Buổi 5). **Không sửa `starter/`** – giữ làm bản gốc.

| Module | Buổi | Vai trò |
|---|---|---|
| `config.py` | 5 | đọc `.env` |
| `logger.py` | 5 | logging có timestamp/level, ghi vào `logs/` |
| `extract_files.py` | 5 | đọc CSV/JSON |
| `transform.py` | 5 | normalize text, email/enum, numeric, datetime |
| `database.py`, `load_postgres.py` | 5–6 | kết nối và upsert vào CORE |
| `api_client.py` | 6 | gọi REST API: pagination, retry, lưu RAW trước transform |
| `validators/schema_validator.py` | 7 | kiểm tra schema/kiểu dữ liệu |
| `validators/business_validator.py` | 7 | kiểm tra business rule |
| `validators/integrity_validator.py` | 7 | kiểm tra toàn vẹn tham chiếu giữa các bảng |
| `quality_report.py` | 7 | sinh DQ report vào `reports/` |
| `refresh_mart.py` | 8 | refresh Data Mart |
| `pipeline.py` | 8 | điều phối end-to-end |

Luồng mục tiêu của Buổi 8:

```
Source (file/API) → RAW → normalize → validate → reject | valid → upsert CORE
→ DQ report → checkpoint/watermark → (tuỳ chọn) refresh MART
```

Thứ tự xử lý theo dependency: `customers → products → orders → order_items → payments`. Checkpoint/watermark chỉ được ghi sau khi run thành công.

Chạy pipeline (sau khi hoàn thiện):

```bash
python -m src.pipeline --source both --input-dir data/incremental/day_2026-07-01 --refresh-mart
```

Chạy public tests:

```bash
pytest tests/test_validators_public.py -v
```

> Giảng viên có bộ **hidden tests** riêng – pass public tests chưa đảm bảo pass toàn bộ.

## 9. Mock REST API

FastAPI chạy tại `http://localhost:8000`, header xác thực `X-API-Key: training-key`.

| Endpoint | Mô tả |
|---|---|
| `GET /health` | health check (không cần key) |
| `GET /customers` | |
| `GET /products` | |
| `GET /orders` | |
| `GET /order-items` | |
| `GET /payments` | |

Query params: `page` (≥1, mặc định 1), `page_size` (1–500, mặc định 100), `updated_after` (ISO 8601, dùng cho incremental load).

Response: `{ "page", "page_size", "total", "has_next", "data": [...] }`.

```bash
curl -H "X-API-Key: training-key" "http://localhost:8000/orders?page=1&page_size=50&updated_after=2026-07-01T00:00:00Z"
```

Swagger UI: `http://localhost:8000/docs`.

## 10. Scripts tiện ích

| Script | Tác dụng |
|---|---|
| `scripts/bootstrap.sh` | khởi động Postgres, **xoá schema `core`/`mart`**, chạy `01_create_oltp.sql`, nạp seed |
| `scripts/bootstrap_core.sh` | tương tự `bootstrap.sh` (chỉ dựng CORE + seed) |
| `scripts/reset.sh` | `docker compose down -v` (xoá cả volume) rồi bootstrap lại từ đầu |
| `scripts/run_daily.sh` | kích hoạt `.venv` và chạy pipeline cho batch 2026-07-01 |
| `scripts/cron_example.txt` | ví dụ lịch cron 02:00 hàng ngày (chỉ đọc/giải thích, không bắt buộc bật) |
| `scripts/preflight_macos.sh` | kiểm tra môi trường trên macOS |

> ⚠️ `bootstrap.sh` và `reset.sh` **xoá dữ liệu hiện có** trong database. Lưu lại kết quả cần thiết trước khi chạy.

## 11. Nộp bài & evidence
- Mỗi buổi lưu minh chứng vào `docs/evidence/` theo quy ước `<buổi>-<nội dung>.<ext>`, ví dụ `01-verify-db.txt`, `02-agg-results.txt`, `03-window-results.txt`.
- Kết quả EXPLAIN lưu ở `docs/explain_output/`.
- Commit sau mỗi buổi với message rõ ràng; **không commit `.env`**, dữ liệu runtime hay `.venv/`.
- Yêu cầu cụ thể từng buổi xem `assignments/session_0X_assignment.md`.

## 12. Troubleshooting

| Triệu chứng | Cách xử lý |
|---|---|
| `port 5432 already in use` | tắt PostgreSQL cài sẵn trên máy, hoặc đổi port trong `docker-compose.yml` và `.env` |
| `bootstrap.sh` lỗi khi tạo bảng/nạp seed | sửa `sql/student/01_create_oltp.sql` trước (tên cột, kiểu dữ liệu, thứ tự bảng cha → con) |
| PowerShell báo lỗi với `<` | dùng `Get-Content ... -Raw \| docker exec -i ...` (xem mục 7) |
| Script `.sh` không chạy trên Windows | chạy bằng Git Bash/WSL; nếu lỗi `\r`, chuyển file về line ending LF |
| API trả `401 Invalid API key` | thiếu/sai header `X-API-Key` hoặc `MOCK_API_KEY` trong `.env` |
| API trả `400` với `updated_after` | giá trị phải là ISO 8601, ví dụ `2026-07-01T00:00:00Z` |
| Muốn làm lại DB từ đầu | `./scripts/reset.sh` |

## 13. Không có trong pack này
Không có `sql/solutions/`, reference `src/`, canonical ERD, Dirty Data Manifest, đáp án quiz, hidden tests, Instructor Guide hay source references. Canonical ERD chỉ được giảng viên reveal sau khi lớp hoàn thành thiết kế ban đầu.
