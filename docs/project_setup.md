# Hướng dẫn khởi tạo dự án và cấu hình Python

Tài liệu này hướng dẫn thiết lập dự án trên Windows bằng PowerShell: tạo môi trường ảo, cài thư viện, cấu hình VS Code, `.env` và các dịch vụ Docker.

Các lệnh bên dưới được chạy từ **thư mục gốc dự án**, nơi có `README.md`, `requirements.txt` và `docker-compose.yml`.

## 1. Môi trường hiện tại và công cụ cần có

Project hiện đã có cấu hình cục bộ:

| Thành phần | Đường dẫn / phiên bản | Vai trò |
|---|---|---|
| Python nền | `.python-runtime/python.exe`, Python 3.12.10 | Python dùng để tạo và chạy môi trường ảo |
| Môi trường ảo | `.venv/` | Chứa thư viện riêng của project |
| Danh sách thư viện | `requirements.txt` | Khai báo thư viện và khoảng phiên bản |
| Cấu hình ứng dụng | `.env` | Thông số kết nối database và API |
| Cấu hình mẫu | `.env.example` | Mẫu cấu hình dùng khi thiết lập trên máy mới |
| Cấu hình VS Code | `.vscode/settings.json` | Chọn Python trong `.venv` làm mặc định |

**Trên máy hiện tại, dùng tiếp `.venv` ở mục 3; không cần tạo lại.** Giữ nguyên `.python-runtime/` vì `.venv` đang tham chiếu Python tại đó. Hai thư mục này được Git bỏ qua nên sẽ không có khi clone project trên máy mới.

Công cụ cần chuẩn bị trên máy mới:

- Python: bộ tài liệu gốc dùng 3.11; môi trường cục bộ hiện tại dùng 3.12.10. Nên dùng cùng phiên bản Python giữa các thành viên khi tái lập môi trường.
- VS Code và extension **Python** của Microsoft.
- Git nếu lấy source bằng Git.
- Docker Desktop có Docker Compose nếu cần PostgreSQL hoặc Mock API. Chỉ cài thư viện và chạy kiểm tra import thì chưa cần Docker.
- Git Bash để chạy các script `.sh` của dự án trên Windows.

Mở project trong VS Code bằng **File → Open Folder**, sau đó mở **Terminal → New Terminal** và chọn PowerShell.

## 2. Tạo `.venv` trên máy mới

Kiểm tra Python đã cài:

```powershell
py -0p
```

Nếu có Python 3.12, tạo môi trường:

```powershell
py -3.12 -m venv .venv
```

Nếu dùng Python 3.11 theo bộ tài liệu gốc:

```powershell
py -3.11 -m venv .venv
```

Chỉ chọn **một** lệnh tạo môi trường phù hợp với Python đã cài. Nếu máy chỉ có lệnh `python`, kiểm tra phiên bản trước khi tạo:

```powershell
python --version
python -m venv .venv
```

Nếu cả `py` và `python` đều không dùng được, cài Python rồi mở terminal mới. Riêng máy hiện tại có thể dùng Python cục bộ để tạo lại môi trường khi cần:

```powershell
.\.python-runtime\python.exe -m venv .venv
```

`venv` là module có sẵn trong bản cài Python đầy đủ; không cần chạy `pip install venv`. Mỗi project nên có một `.venv` riêng. Không copy `.venv` giữa các máy hoặc đổi vị trí thư mục project rồi tiếp tục dùng môi trường cũ; hãy tạo lại bằng Python trên máy đích.

## 3. Kích hoạt và kiểm tra môi trường

Kích hoạt trong PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Terminal thường hiển thị tiền tố `(.venv)`. Kiểm tra chính xác Python đang chạy:

```powershell
python -c "import sys; print(sys.executable); print('venv:', sys.prefix != sys.base_prefix)"
python -m pip --version
```

Kết quả mong đợi:

- `sys.executable` kết thúc bằng `.venv\Scripts\python.exe` trong project này.
- Dòng `venv: True`.
- Đường dẫn của pip nằm trong `.venv`.

Nếu PowerShell chặn `Activate.ps1`, có thể dùng trực tiếp Python trong môi trường, không cần kích hoạt:

```powershell
.\.venv\Scripts\python.exe -m pip --version
```

Hoặc cho phép script trong **phiên terminal hiện tại** rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Nếu máy do tổ chức quản lý và chính sách vẫn chặn script, dùng đường dẫn Python trực tiếp như trên.

Thoát môi trường khi kết thúc:

```powershell
deactivate
```

Mở terminal mới thì cần kích hoạt lại nếu VS Code chưa tự kích hoạt.

## 4. Cài đặt và quản lý thư viện

Sau khi kích hoạt `.venv`, cài các thư viện được khai báo trong project:

```powershell
python -m pip install -r requirements.txt
python -m pip check
```

Nếu chưa kích hoạt môi trường, dùng:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

`pip check` báo `No broken requirements found.` khi các dependency đã cài không có xung đột khai báo. Dùng `python -m pip` giúp cài thư viện vào đúng Python đang chọn.

### Các thư viện của project

| Khai báo trong `requirements.txt` | Mục đích |
|---|---|
| `pandas>=2.2,<3` | Đọc, làm sạch và xử lý dữ liệu dạng bảng |
| `requests>=2.32,<3` | Gọi REST API |
| `SQLAlchemy>=2.0,<3` | Làm việc với database bằng Python |
| `psycopg[binary]>=3.2,<4` | Driver kết nối PostgreSQL |
| `python-dotenv>=1.0,<2` | Đọc biến cấu hình từ `.env` |
| `pytest>=8,<9` | Chạy kiểm thử |
| `fastapi>=0.115,<1` | Xây dựng Mock REST API |
| `uvicorn[standard]>=0.30,<1` | Chạy ứng dụng FastAPI |
| `matplotlib>=3.9,<4` | Vẽ biểu đồ |

Ví dụ `pandas>=2.2,<3` cho phép pip chọn phiên bản từ 2.2 đến trước 3.0. Vì đây là khoảng phiên bản, hai lần cài ở thời điểm khác nhau có thể nhận phiên bản khác nhau.

### Thêm hoặc cập nhật thư viện

1. Thêm tên thư viện và giới hạn phiên bản phù hợp vào `requirements.txt`.
2. Chạy lại `python -m pip install -r requirements.txt`.
3. Chạy `python -m pip check` và các bài test liên quan trước khi commit thay đổi.

Xem các phiên bản đang cài:

```powershell
python -m pip list
```

Khi cần ghi lại chính xác phiên bản để tái lập môi trường, tạo bản chụp riêng:

```powershell
python -m pip freeze | Set-Content -Encoding utf8 requirements-lock.txt
```

Trên môi trường ảo mới, cùng phiên bản Python và hệ điều hành, cài bản chụp đó bằng:

```powershell
python -m pip install -r requirements-lock.txt
```

`requirements-lock.txt` chỉ được tạo khi chạy lệnh trên. Bản chụp này bao gồm cả thư viện phụ thuộc; giữ `requirements.txt` làm danh sách khai báo chính của project.

Mock API chạy trong Docker cài thư viện từ `mock_api/requirements.txt` bên trong image. Cài vào `.venv` không cập nhật thư viện trong container. Sau khi sửa requirements của Mock API, build lại bằng `docker compose up -d --build mock-api`.

## 5. Chọn Python trong VS Code

1. Nhấn `Ctrl+Shift+P`.
2. Chọn **Python: Select Interpreter**.
3. Chọn Python tại `.venv\Scripts\python.exe`. Nếu chưa thấy, chọn **Enter interpreter path** và trỏ đến file đó.
4. Mở terminal mới và kiểm tra `python -c "import sys; print(sys.executable)"`.

Cấu hình hiện tại trong `.vscode/settings.json`:

```json
{
    "python.terminal.useEnvFile": true,
    "python.defaultInterpreterPath": "${workspaceFolder}\\.venv\\Scripts\\python.exe"
}
```

Nếu VS Code đã ghi nhớ một interpreter khác, chọn lại bằng **Python: Select Interpreter**. `.vscode/` đang được Git bỏ qua nên máy mới cần tự chọn interpreter hoặc tạo cấu hình này.

## 6. Tạo cấu hình `.env`

Chỉ sao chép cấu hình mẫu nếu chưa có `.env`, để giữ cấu hình đang sử dụng:

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

Các giá trị mẫu cho môi trường thực hành local:

```dotenv
POSTGRES_DB=ecommerce
POSTGRES_USER=de_user
POSTGRES_PASSWORD=de_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://de_user:de_password@localhost:5432/ecommerce
MOCK_API_URL=http://localhost:8000
MOCK_API_KEY=training-key
```

`src/config.py` đọc `.env` ở thư mục gốc qua `python-dotenv`. Python dùng `DATABASE_URL` để kết nối database, vì vậy khi đổi host, port, user hoặc mật khẩu, cần cập nhật cả URL này. Mật khẩu có ký tự đặc biệt cần được mã hóa URL trong chuỗi kết nối.

Docker Compose hiện ánh xạ cố định `5432:5432` và `8000:8000`. Nếu cổng 5432 trên máy đã được sử dụng, có thể đổi mapping thành `5433:5432`, rồi sửa `POSTGRES_PORT=5433` và cổng trong `DATABASE_URL` thành `5433`.

`.env` và `.venv` khác nhau: `.env` chứa **cấu hình ứng dụng**, còn `.venv/` chứa **môi trường Python và thư viện**. Không commit `.env`, `.venv/` hoặc `.python-runtime/`; `.gitignore` hiện đã bỏ qua các mục này.

## 7. Khởi động PostgreSQL và Mock API

Mở Docker Desktop, chờ Docker hoạt động, rồi chạy:

```powershell
docker compose up -d postgres mock-api
docker compose ps
```

Chờ PostgreSQL có trạng thái `healthy`. Kiểm tra API:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/health
```

Swagger UI: `http://localhost:8000/docs`.

Lệnh khởi động container chỉ tạo dịch vụ; chưa chạy SQL của học viên để dựng bảng và nạp seed. Xem [hướng dẫn Database & SQL](../sql/README.md) để chuẩn bị database theo bài học.

Nếu dùng `scripts/bootstrap.sh`, hãy hoàn thiện `sql/student/01_create_oltp.sql` trước. Chạy từ **Git Bash** tại thư mục gốc:

```bash
bash scripts/bootstrap.sh
```

**Script bootstrap xóa schema `core` và `mart` trước khi tạo lại và nạp seed.** Chỉ chạy khi muốn khởi tạo hoặc dựng lại database thực hành.

## 8. Kiểm tra thiết lập

Trong PowerShell, kiểm tra import thư viện bằng Python của `.venv`:

```powershell
.\.venv\Scripts\python.exe -c "import pandas, requests, sqlalchemy, psycopg, dotenv, pytest, fastapi, uvicorn, matplotlib; print('Import OK')"
.\.venv\Scripts\python.exe -m pip check
```

Chạy public tests của bài Data Quality khi cần kiểm tra phần bài làm:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_validators_public.py -v
```

Import thành công xác nhận thư viện tải được; test còn phụ thuộc vào nội dung bài làm. Nếu test lỗi, đọc traceback để phân biệt thiếu dependency, sai cấu hình kết nối và lỗi logic trong code.

Thư mục `src/` đã có trong project hiện tại. Khi thiết lập từ một bản student pack chưa có `src/`, sao chép `starter/src/` sang `src/` một lần và giữ nguyên bản starter.

## 9. Quy trình sử dụng hằng ngày

```powershell
# Chạy tại thư mục gốc project
.\.venv\Scripts\Activate.ps1

# Cài bổ sung nếu requirements.txt vừa thay đổi
python -m pip install -r requirements.txt

# Chỉ cần khi bài thực hành sử dụng database/API
docker compose up -d postgres mock-api

# Kiểm tra bài Data Quality khi cần
python -m pytest tests/test_validators_public.py -v

# Thoát môi trường Python sau khi làm việc
deactivate
```

Dừng các dịch vụ khi không dùng:

```powershell
docker compose stop
```

## 10. Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `python` không được nhận diện | Dùng `.\.venv\Scripts\python.exe`; trên máy mới, kiểm tra Python đã cài và mở terminal mới |
| `py` báo không tìm thấy Python | Máy hiện tại dùng `.python-runtime`; trên máy mới cần cài Python trước khi tạo venv |
| PowerShell chặn `Activate.ps1` | Dùng Python trực tiếp hoặc cấu hình execution policy cho phiên terminal ở mục 3 |
| `ModuleNotFoundError` | Kiểm tra `sys.executable`, rồi cài `requirements.txt` bằng chính interpreter đó |
| VS Code báo thiếu thư viện dù đã cài | Chọn lại `.venv\Scripts\python.exe` và mở terminal mới |
| pip lỗi kết nối / proxy / chứng chỉ | Kiểm tra mạng và proxy của máy; dùng chứng chỉ được tổ chức cung cấp nếu có |
| `.venv` lỗi sau khi di chuyển project | Giữ source và requirements, tạo lại môi trường ở vị trí mới bằng Python đã cài |
| Kết nối PostgreSQL bị từ chối | Kiểm tra Docker Desktop, `docker compose ps`, cổng mapping và `DATABASE_URL` |
| Đổi `.env` nhưng tài khoản PostgreSQL không đổi | Các biến khởi tạo PostgreSQL chỉ có tác dụng khi tạo data directory lần đầu; sửa tài khoản trong DB hoặc chủ động dựng lại DB sau khi sao lưu |
| API trả `401` | Kiểm tra `MOCK_API_KEY` và header `X-API-Key` của request |

Hướng dẫn macOS có sẵn tại [scripts/setup_macos.md](../scripts/setup_macos.md). Trên macOS, đường dẫn Python của venv là `.venv/bin/python` và lệnh kích hoạt là `source .venv/bin/activate`. Nếu dùng WSL, tạo môi trường Python riêng bên trong WSL.
