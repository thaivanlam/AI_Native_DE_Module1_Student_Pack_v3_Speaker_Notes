# 1. Tổng quan project

← [Mục lục](README.md) · Tiếp: [2. Kiến trúc](02_kien_truc.md) →

## 1.1 Project là gì?

**AI-Native Data Engineering – Module 1 – Student Pack** là bộ tài liệu thực hành 8 buổi (mỗi buổi 90 phút lab). Toàn bộ 8 buổi xoay quanh **một bài toán xuyên suốt**: xây dựng hệ thống dữ liệu cho một doanh nghiệp E-commerce đa danh mục.

Repo này vừa là **học liệu** (slide, lab, bài tập, quiz) vừa là **workspace** nơi học viên viết SQL, Python và lưu minh chứng (evidence) sau mỗi buổi.

> Đây là bản **Speaker Notes edition**: các slide `.pptx` trong `slides/` có ghi chú giảng dạy ở Notes pane.

## 1.2 Bài toán nghiệp vụ

Doanh nghiệp có dữ liệu phát sinh từ 4 nguồn nghiệp vụ: **khách hàng, catalog sản phẩm, đơn hàng, thanh toán**. Nhóm Data Engineering cần:

1. Lưu trữ dữ liệu giao dịch chuẩn hoá, có ràng buộc toàn vẹn (OLTP).
2. Trả lời các câu hỏi kinh doanh và tính KPI hằng ngày.
3. Tiếp nhận dữ liệu mới **tự động mỗi ngày** từ file và REST API, lọc bỏ dữ liệu lỗi, không tạo trùng lặp.

### KPI cần hỗ trợ (theo [docs/business_requirements.md](../docs/business_requirements.md))

| KPI | Định nghĩa ngắn |
|---|---|
| Total Revenue | Doanh thu net của đơn `completed` |
| Total Orders | Số đơn |
| AOV | Doanh thu / số đơn |
| Active / New Customers | Khách có mua / khách mới |
| Payment Success Rate | Tỷ lệ payment `success` |
| Revenue breakdown | Theo category, product, segment, channel |
| Top customers/products | Xếp hạng |
| Running revenue | Luỹ kế theo ngày, tháng |
| Cohort | Theo tháng phát sinh đơn đầu tiên |

## 1.3 Lộ trình 8 buổi

```
Buổi 1        Buổi 2–3          Buổi 4          Buổi 5–6               Buổi 7          Buổi 8
ERD + OLTP → SQL Analytics  → Data Mart   → Python ingestion   → Data Quality → Daily pipeline
 (core)      (KPI, cohort)     (mart)        (file + API)           (reject)       (tự động hoá)
```

| Buổi | Chủ đề | Sản phẩm chính | Dữ liệu dùng |
|---|---|---|---|
| 1 | Tổng quan hệ thống dữ liệu & thiết kế DB | ERD `database/ecommerce_oltp.dbml`, DDL `01_create_oltp.sql` | — |
| 2 | SQL thực chiến cho Business Analytics | `02_exercises_basic.sql`, EXPLAIN / index | `data/seed/` |
| 3 | SQL nâng cao: CTE, Window, RFM, Cohort | `03_*.sql`, heatmap cohort | `data/seed/` |
| 4 | Thiết kế Sales Data Mart (Star Schema) | `04_data_mart.sql` | `data/seed/` |
| 5 | Python cơ bản cho pipeline | `extract_files.py`, `transform.py`, `logger.py` | `data/incremental/` |
| 6 | Ingestion từ REST API | `api_client.py`, `load_postgres.py` (upsert) | Mock API |
| 7 | Data Cleaning & Data Quality | `validators/`, reject/quarantine, DQ report | `data/dirty/` |
| 8 | Tự động hoá daily pipeline | `pipeline.py`, checkpoint, `run_daily.sh`, cron | incremental + API |

Kết thúc module bằng **mini project** ([assignments/mini_project.md](../assignments/mini_project.md)): *Automated E-commerce Data Ingestion Pipeline* – demo 5–7 phút.

| Tiêu chí chấm mini project | Trọng số |
|---|---:|
| OLTP / Data Mart | 20% |
| SQL Analytics | 15% |
| Python ingestion | 20% |
| Data Quality | 20% |
| Idempotency / automation / logging | 15% |
| Demo / README | 10% |

## 1.4 Bốn nguyên tắc xuyên suốt

| Nguyên tắc | Ý nghĩa thực tế |
|---|---|
| **Không sửa RAW** | File nguồn trong `data/` và bản chụp `data/raw/` là bất biến. Làm sạch chỉ diễn ra ở bước transform. |
| **Idempotent / rerun-safe** | Chạy lại script SQL hay pipeline cùng batch phải ra cùng kết quả, không nhân đôi dữ liệu (dùng `IF NOT EXISTS`, `ON CONFLICT DO UPDATE`). |
| **Đối soát được** | `Input = Valid + Rejected`; row count, reject count, DQ report phải khớp và có evidence. |
| **Không hard-code secret** | Mọi thông số kết nối đọc từ `.env` (mẫu ở `.env.example`). |

## 1.5 Những gì KHÔNG có trong pack

Không có đáp án chính thức (`sql/solutions/`, reference `src/`), canonical ERD, Dirty Data Manifest, đáp án quiz, hidden tests hay Instructor Guide. Một số lab vẫn nhắc tới `sql/solutions/...` – đó là tài liệu của giảng viên, học viên không nhận được.
