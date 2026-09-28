# 11. Trạng thái project

← [10. Vận hành](10_van_hanh.md) · [Về mục lục](README.md)

Cập nhật theo commit `ec423d2` (2026-09-28).

## 11.1 Tổng quan tiến độ

| Buổi | Chủ đề | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | ERD + OLTP | ✅ Hoàn thành (kèm bonus CHECK/DEFAULT) | `database/ecommerce_oltp.dbml`, `01_create_oltp.sql`, `docs/evidence/01-*`, `reflection_01.md` |
| 2 | SQL cơ bản + business questions | ✅ Hoàn thành (kèm bonus 2.1, 2.2) | `02_exercises_basic.sql`, `03_exercises_advanced.sql`, `05_performance_index.sql`, `docs/evidence/02-*`, `answers_02.md`, `explain_output/` |
| 3 | CTE, Window, RFM, Cohort | ✅ Hoàn thành (kèm bonus RFM score, time series) | `03_cte_window_cohort.sql`, `docs/evidence/03-*`, `cohort_retention.csv`, `customer_rfm.csv`, `reflection_03.md` |
| 4 | Sales Data Mart | ⏳ Chưa làm | `04_data_mart.sql` chỉ có TODO |
| 5 | Python cơ bản | ⏳ Chưa làm | Chưa có `src/` (mới có `starter/src/`) |
| 6 | Ingestion REST API | ⏳ Chưa làm | Mock API đã có sẵn và chạy được |
| 7 | Data Quality | ⏳ Chưa làm | Public tests có sẵn, chưa pass (validator chưa implement) |
| 8 | Daily pipeline | ⏳ Chưa làm | `run_daily.sh`, `cron_example.txt` có sẵn |

## 11.2 Lịch sử commit gần đây

| Commit | Nội dung |
|---|---|
| `ec423d2` | Time series: tăng trưởng doanh thu, moving average |
| `0f12955` | Phân khúc khách hàng nâng cao: RFM score, LTV |
| `365ee48` | Cohort retention + heatmap |
| `c48b577` | Bài tập SQL nâng cao: customer analytics, cohort |
| `4ac2d42` | CTE cho retention và cohort tracking |

## 11.3 Việc tiếp theo (theo thứ tự phụ thuộc)

1. **Buổi 4** – Chốt grain, viết DDL + load cho schema `mart`, 5 query đối soát OLTP ↔ Mart.
2. **Buổi 5** – `cp -R starter/src src`; implement `extract_files`, `transform.normalize`, `logger`; profile batch 2026-07-01.
3. **Buổi 6** – `api_client.fetch_all_pages` (pagination + retry + RAW), `load_postgres.upsert_dataframe`; chứng minh chạy 2 lần không trùng.
4. **Buổi 7** – 3 validator + `quality_report`; chạy dirty batch 2026-07-02, pass `pytest tests/test_validators_public.py`.
5. **Buổi 8** – `pipeline.run` + CLI, checkpoint, `refresh_mart`; demo mini project.

## 11.4 Lưu ý đã phát hiện khi đọc code

- **BQ1 (doanh thu tháng 7) = 0** là đúng với dữ liệu hiện tại: seed dừng ở 29/06. Sau khi pipeline nạp batch 2026-07-01, câu này sẽ ra 361 đơn / 4,37 tỷ VND – đây là cách kiểm chứng tốt cho Buổi 8.
- **RFM dùng `NOW()`** nên `recency_days` thay đổi theo ngày chạy (ví dụ `CUS000001`: 104 trong `customer_rfm.csv`, 105 trong `03-rfm-segments.csv`). Khi so sánh evidence cần ghi rõ thời điểm chạy.
- **CHECK `order_date <= NOW()` / `payment_date <= NOW()`** (bonus Buổi 1) sẽ từ chối dữ liệu có ngày tương lai – cần nhớ khi test pipeline với dữ liệu giả lập ngày tới.
- Các lab nhắc tới `sql/solutions/...` – thư mục này **không có** trong Student Pack.
