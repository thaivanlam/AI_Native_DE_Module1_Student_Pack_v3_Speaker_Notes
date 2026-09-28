# 10. Vận hành: cài đặt, chạy, xử lý lỗi

← [9. Mock API](09_mock_api.md) · Tiếp: [11. Trạng thái](11_trang_thai.md) →

## 10.1 Yêu cầu môi trường

| Công cụ | Phiên bản | Dùng cho |
|---|---|---|
| Docker Desktop | mới nhất | PostgreSQL 16 + Mock API |
| Python | 3.11 | Từ Buổi 5 |
| Git | bất kỳ | Commit evidence |
| DBeaver | Community (khuyến nghị) | Xem ERD, chạy query |
| VS Code | (khuyến nghị) | |

Windows: chạy các script `.sh` bằng **Git Bash** hoặc **WSL**.

## 10.2 Biến môi trường (`.env`)

| Biến | Mặc định |
|---|---|
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `ecommerce` / `de_user` / `de_password` |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5432` |
| `DATABASE_URL` | `postgresql+psycopg://de_user:de_password@localhost:5432/ecommerce` |
| `MOCK_API_URL` / `MOCK_API_KEY` | `http://localhost:8000` / `training-key` |

`.env` bị `.gitignore` – **không commit**.

## 10.3 Khởi động từ đầu

```bash
# 1. Cấu hình
cp .env.example .env

# 2. PostgreSQL
docker compose up -d postgres
docker compose ps                  # chờ "healthy"

# 3. Tạo schema core + nạp seed (cần 01_create_oltp.sql đúng)
./scripts/bootstrap.sh

# 4. Python (từ Buổi 5)
python3.11 -m venv .venv
source .venv/bin/activate          # Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt
[ -d src ] || cp -R starter/src src

# 5. Mock API (từ Buổi 6)
docker compose up -d mock-api
curl http://localhost:8000/health
```

## 10.4 Chạy SQL

```bash
# Bash / Git Bash
docker exec -i ecommerce-postgres psql -U de_user -d ecommerce -v ON_ERROR_STOP=1 < sql/student/02_exercises_basic.sql
```

```powershell
# PowerShell (không có redirect "<")
Get-Content sql/student/02_exercises_basic.sql -Raw | docker exec -i ecommerce-postgres psql -U de_user -d ecommerce -v ON_ERROR_STOP=1
```

psql tương tác: `docker exec -it ecommerce-postgres psql -U de_user -d ecommerce`.

## 10.5 Scripts tiện ích

| Script | Làm gì | Cảnh báo |
|---|---|---|
| [bootstrap.sh](../scripts/bootstrap.sh) | Start Postgres → **DROP schema `core`, `mart`** → chạy `01_create_oltp.sql` → `\copy` 7 file seed theo thứ tự cha→con | ⚠️ Xoá dữ liệu |
| [bootstrap_core.sh](../scripts/bootstrap_core.sh) | Giống `bootstrap.sh` | ⚠️ Xoá dữ liệu |
| [reset.sh](../scripts/reset.sh) | `docker compose down -v` (xoá volume) rồi bootstrap | ⚠️ Xoá toàn bộ DB |
| [run_daily.sh](../scripts/run_daily.sh) | Kích hoạt `.venv`, chạy pipeline batch 2026-07-01 với `--refresh-mart` | Cần `src/pipeline.py` hoàn thiện |
| [cron_example.txt](../scripts/cron_example.txt) | Ví dụ cron `0 2 * * *` (02:00 hằng ngày) | Chỉ để đọc hiểu |
| [preflight_macos.sh](../scripts/preflight_macos.sh) | Kiểm tra brew, git, python3.11, docker, code | macOS |
| [cohort_heatmap.py](../scripts/cohort_heatmap.py) | Đọc `docs/cohort_retention.csv` → `docs/evidence/03-cohort.png` | — |

## 10.6 Nộp bài & evidence

1. Lưu minh chứng vào `docs/evidence/` theo quy ước `<buổi>-<nội dung>.<ext>`.
2. Kết quả EXPLAIN lưu ở `docs/explain_output/`.
3. Commit sau mỗi buổi: `session-0X: <mô tả>`.
4. Không commit `.env`, `.venv/`, dữ liệu runtime.
5. Yêu cầu cụ thể từng buổi: `assignments/session_0X_assignment.md`.

## 10.7 Troubleshooting

| Triệu chứng | Cách xử lý |
|---|---|
| `port 5432 already in use` | Tắt PostgreSQL cài sẵn trên máy, hoặc đổi port trong `docker-compose.yml` và `.env` |
| `bootstrap.sh` lỗi khi tạo bảng/nạp seed | Sửa `01_create_oltp.sql` (tên cột, kiểu, thứ tự cha→con) |
| PowerShell lỗi với `<` | Dùng `Get-Content … -Raw \| docker exec -i …` |
| Script `.sh` lỗi trên Windows | Chạy bằng Git Bash/WSL; lỗi `\r` → đổi line ending sang LF |
| API `401 Invalid API key` | Thiếu/sai `X-API-Key` hoặc `MOCK_API_KEY` |
| API `400` với `updated_after` | Dùng ISO 8601, ví dụ `2026-07-01T00:00:00Z` |
| Muốn làm lại DB từ đầu | `./scripts/reset.sh` |
