# 3. Cấu trúc thư mục

← [2. Kiến trúc](02_kien_truc.md) · Tiếp: [4. Dữ liệu](04_du_lieu.md) →

## 3.1 Cây thư mục

```
.
├── README.md                 # Hướng dẫn chính của pack
├── SPEAKER_NOTES_EDITION.md  # Ghi chú về bản slide có Speaker Notes
├── docker-compose.yml        # Postgres 16 + Mock API
├── requirements.txt          # Thư viện Python
├── .env.example              # Mẫu biến môi trường (copy thành .env)
│
├── slides/                   # 8 slide deck .pptx (có Speaker Notes)
├── labs/                     # session_01.md … session_08.md – hướng dẫn thực hành
├── assignments/              # Bài tập sau mỗi buổi + mini_project.md
├── quizzes/                  # Quiz từng buổi (.csv, không kèm đáp án)
│
├── docs/                     # Tài liệu nghiệp vụ + kết quả + evidence
│   ├── business_requirements.md
│   ├── data_contract.md
│   ├── data_dictionary.csv
│   ├── dataset_summary.json
│   ├── answers_02.md         # Đáp án BQ1–BQ5 Buổi 2
│   ├── reflection_01.md/.docx, reflection_03.md
│   ├── cohort_retention.csv  # Ma trận cohort Buổi 3
│   ├── customer_rfm.csv      # Bảng RFM Buổi 3
│   ├── query_results.csv     # Kết quả truy vấn tổng hợp
│   ├── evidence/             # Minh chứng theo buổi: 01-*, 02-*, 03-*
│   └── explain_output/       # Báo cáo EXPLAIN ANALYZE / index
│
├── database/
│   └── ecommerce_oltp.dbml   # ERD (dbdiagram.io)
│
├── sql/
│   ├── README.md             # Thứ tự chạy + câu verify + quan hệ bảng
│   └── student/
│       ├── 01_create_oltp.sql          # DDL schema core
│       ├── 02_exercises_basic.sql      # Q1–Q15, BQ1–BQ5
│       ├── 03_cte_window_cohort.sql    # CTE, Window, RFM, Cohort, TS
│       ├── 03_exercises_advanced.sql   # Bonus window: luỹ kế, tỷ trọng, churn
│       ├── 04_data_mart.sql            # (TODO) Sales Data Mart
│       ├── 05_performance_index.sql    # Đo EXPLAIN trước/sau index
│       └── tests/01_bonus_constraint_tests.sql
│
├── data/
│   ├── seed/                 # Baseline cho CORE (Buổi 2–4)
│   ├── incremental/day_2026-07-01/   # Batch SẠCH (Buổi 5, 6, 8)
│   ├── dirty/day_2026-07-02/         # Batch BẨN (Buổi 7)
│   ├── raw/                  # (runtime) bản chụp RAW
│   └── reject/               # (runtime) bản ghi bị quarantine
│
├── starter/src/              # Skeleton Python – KHÔNG sửa, copy sang src/
├── mock_api/                 # FastAPI giả lập nguồn REST
├── tests/                    # Public pytest cho validators
├── scripts/                  # bootstrap / reset / run_daily / cron / heatmap
├── metadata/                 # (runtime) checkpoint/watermark
├── reports/                  # (runtime) DQ report
└── logs/                     # (runtime) log pipeline
```

## 3.2 Nhóm thư mục theo vai trò

| Vai trò | Thư mục | Ai sửa? |
|---|---|---|
| **Học liệu** (chỉ đọc) | `slides/`, `labs/`, `assignments/`, `quizzes/` | Giảng viên |
| **Đặc tả nghiệp vụ** (chỉ đọc) | `docs/business_requirements.md`, `data_contract.md`, `data_dictionary.csv` | Giảng viên |
| **Dữ liệu nguồn** (bất biến) | `data/seed/`, `data/incremental/`, `data/dirty/`, `mock_api/data/` | Không ai |
| **Workspace học viên** | `database/`, `sql/student/`, `src/` (tạo từ `starter/src/`) | Học viên |
| **Minh chứng / kết quả** | `docs/evidence/`, `docs/explain_output/`, `docs/*.csv`, `docs/answers_*.md` | Học viên |
| **Hạ tầng & tiện ích** | `docker-compose.yml`, `mock_api/`, `scripts/` | Có sẵn (chỉ `run_daily.sh` học viên hoàn thiện) |
| **Runtime** (gitignored) | `data/raw/`, `data/reject/`, `logs/`, `reports/`, `metadata/` | Pipeline tự sinh |

## 3.3 Quy ước đặt tên

- **Evidence:** `docs/evidence/<buổi>-<nội dung>.<ext>` – ví dụ `01-verify-db.txt`, `02-agg-results.txt`, `03-cohort.png`.
- **SQL:** tiền tố số theo buổi – `01_` (Buổi 1), `02_` (Buổi 2), `03_` (Buổi 3), `04_` (Buổi 4), `05_` (hiệu năng, bài 2.2).
- **Commit:** `session-0X: <mô tả ngắn>`.
- **Batch dữ liệu:** `day_YYYY-MM-DD/` với file `<entity>_daily.csv` và `payments_daily.json`.
