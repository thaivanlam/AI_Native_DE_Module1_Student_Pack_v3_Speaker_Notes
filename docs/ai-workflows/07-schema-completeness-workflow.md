# Bài 1: Schema & Completeness Validation — Quy trình xử lý với AI

Tài liệu mô tả các bước thực tế đã thực hiện, cơ sở cho các quyết định kỹ thuật và kết quả xác minh. Đây là bản giải thích quy trình có thể kiểm chứng, không phải bản ghi suy nghĩ nội bộ của AI.

## 1. Mục tiêu và đầu ra

Bài 1 yêu cầu kiểm tra cấu trúc và độ đầy đủ dữ liệu của 5 bảng: `customers`, `products`, `orders`, `order_items`, `payments`.

- Thiếu cột bắt buộc: phát sinh `ValueError`, kèm tên bảng và danh sách cột thiếu.
- Thiếu giá trị bắt buộc: ghi nhận `MISSING_REQUIRED` cho dòng tương ứng.
- Chấm điểm completeness cho từng dòng từ 0 đến 100.
- Chạy trên `data/dirty/day_2026-07-02/` và ghi 10 dòng đầu mỗi bảng vào `docs/evidence/07-schema.txt`.

## 2. Các bước AI đã thực hiện

### Bước 1 — Đọc yêu cầu và khảo sát mã hiện có

AI đọc đề Bài 1, `docs/data_contract.md`, validator, pipeline, các kiểm thử hiện có và log minh chứng. Đồng thời kiểm tra trạng thái Git để nhận biết các thay đổi đã có trong workspace.

Kết quả: `src/validators/schema_validator.py` đã có phần triển khai chính và file minh chứng đã tồn tại. Vì vậy, công việc tập trung vào kiểm tra và bổ sung các trường hợp biên thay vì viết lại toàn bộ. Các thay đổi Bài 8 được giữ ngoài commit Bài 1.

Lưu ý về nguồn quy định: `docs/data_contract.md` mô tả ID, thời gian, tiền, enum và cột audit nhưng không liệt kê đầy đủ ma trận cột bắt buộc. Lần xử lý này giữ nguyên danh sách `REQUIRED` đã có trong validator; không tự thêm các cột audit vào điều kiện completeness.

### Bước 2 — Phân biệt lỗi cấu trúc và lỗi giá trị

Hai trường hợp cần cách xử lý riêng:

| Trường hợp | Ví dụ | Kết quả |
|---|---|---|
| Thiếu cột cấu trúc | Bảng customers không có cột email | `ValueError` trước khi chấm điểm |
| Có cột nhưng thiếu giá trị | Có cột full_name, một dòng chứa NULL | Dòng đó có `MISSING_REQUIRED` và giảm điểm |

`validate_schema(name, df)` so sánh tên cột thực tế với `REQUIRED[name]`. Cột bổ sung vẫn được chấp nhận.

### Bước 3 — Kiểm tra completeness

`is_missing(value)` nhận diện `None`, `NaN`, `pd.NA`, `NaT`, chuỗi rỗng và chuỗi chỉ có khoảng trắng. Việc dùng `strip()` giúp phát hiện cả giá trị như `' \t '`.

Giá trị số `0` được xem là có dữ liệu. Việc số đó có phù hợp quy tắc nghiệp vụ hay không thuộc bước kiểm tra khác.

Danh sách dùng trong lần xử lý này:

| Bảng | REQUIRED và REQUIRED_VALUES |
|---|---|
| customers | customer_id, full_name, email, status |
| products | product_id, category_id, product_name, unit_price, status |
| orders | order_id, customer_id, order_date, status, order_total |
| order_items | order_item_id, order_id, product_id, quantity, unit_price, discount_amount |
| payments | payment_id, order_id, payment_date, payment_status, amount |

`REQUIRED_VALUES` được tạo bằng cách sao chép từng danh sách trong `REQUIRED`. Điều này cho phép điều chỉnh yêu cầu giá trị sau này mà không vô tình thay đổi yêu cầu cấu trúc.

### Bước 4 — Chấm điểm từng dòng

`score_rows(name, df)` trả về bốn cột: `row_id`, `score`, `errors`, `missing_cols`.

```text
score = round(100 × số trường bắt buộc có giá trị / tổng số trường bắt buộc)
```

Ví dụ: customers có 4 trường bắt buộc; thiếu full_name thì còn 3 trường có giá trị, đạt `round(100 × 3/4) = 75` điểm.

Nếu thiếu nhiều trường, `missing_cols` liệt kê toàn bộ trường thiếu; `errors` chứa mã `MISSING_REQUIRED` một lần. Điểm được làm tròn thành số nguyên theo `round()` của Python, ví dụ 5/6 trường đạt 83 điểm.

Điểm 100 chỉ xác nhận completeness theo danh sách trên. Email sai định dạng, giá âm, ID trùng hoặc khóa ngoại không tồn tại vẫn có thể đạt 100 điểm ở Bài 1.

### Bước 5 — Bổ sung xử lý trường hợp biên

AI thực hiện ba thay đổi trong validator:

1. Sao chép độc lập danh sách `REQUIRED_VALUES` từ `REQUIRED`.
2. Gọi `validate_schema()` ngay đầu `score_rows()`, để gọi trực tiếp hàm chấm điểm trên bảng thiếu cột cũng nhận được `ValueError` rõ ràng.
3. Khai báo rõ bốn cột đầu ra khi tạo DataFrame kết quả, để bảng rỗng vẫn giữ cấu trúc và có thể truy cập cột `score`.

Phần sửa này không bổ sung luồng reject completeness vào pipeline. Phạm vi thực hiện là validator, kiểm thử và minh chứng của Bài 1.

### Bước 6 — Viết và chạy kiểm thử

File `tests/test_schema_validator.py` bổ sung 17 ca kiểm thử sau khi mở rộng tham số:

| Nhóm kiểm thử | Số ca | Điều được xác minh |
|---|---:|---|
| Thiếu cột trên 5 bảng | 5 | `ValueError` chứa tên bảng và các cột thiếu |
| Các dạng missing | 6 | NULL và chuỗi trắng giảm điểm đúng; dòng đầy đủ đạt 100; dữ liệu đầu vào không bị thêm cột score |
| Toàn bộ giá trị thiếu và bảng rỗng | 5 | Điểm 0 khi thiếu toàn bộ; bảng rỗng vẫn có đủ cột kết quả |
| Số 0 và làm tròn | 1 | Số 0 không bị coi là missing; 5/6 trường đạt 83 điểm |

Chạy thêm 4 kiểm thử validator công khai để kiểm tra các hành vi nghiệp vụ mẫu vẫn hoạt động.

Lần đầu chưa chạy được vì `python` không có trong PATH và launcher `py` không tìm thấy bản Python đã đăng ký. Sau khi kiểm tra ngoài sandbox, AI tìm thấy Python 3.11 tại `C:/Users/MSI/AppData/Local/Programs/Python/Python311/python.exe`. Bản này thiếu pytest, nên AI cài pandas và pytest cùng các dependency vào `.test-deps/` trong dự án, rồi thiết lập `PYTHONPATH` để sử dụng.

Kết quả chạy thực tế: **21 passed in 8.49s**, không có ca thất bại.

### Bước 7 — Tạo lại minh chứng trên dữ liệu dirty

AI chạy module `src.validators.schema_validator`. Module đọc cả 5 bảng, kiểm tra cấu trúc, chấm điểm toàn bộ các dòng và ghi 10 dòng đầu mỗi bảng vào `docs/evidence/07-schema.txt`.

| Bảng | Số dòng | Thiếu cột bắt buộc | Số dòng thiếu giá trị bắt buộc |
|---|---:|---|---:|
| customers | 40 | Không | 1 |
| products | 30 | Không | 0 |
| orders | 100 | Không | 0 |
| order_items | 220 | Không | 0 |
| payments | 90 | Không | 0 |

Tổng cộng 480 dòng được chấm điểm. Dòng `CUS000004` thiếu `full_name`, đạt 75 điểm; 479 dòng còn lại đạt 100 điểm completeness.

```text
row_id=CUS000004 score=75 errors=[MISSING_REQUIRED]
  -> missing_cols=['full_name']
```

Minh chứng được tạo lại thành công và có nội dung giống bản đã được Git theo dõi, nên không xuất hiện trong diff commit.

### Bước 8 — Commit và push theo yêu cầu

AI thêm `.test-deps/` vào `.gitignore` để thư viện cài cục bộ không đi vào repository. Sau đó commit validator, bộ kiểm thử và thay đổi `.gitignore`.

- Commit: `18772b0` — `Complete schema validation edge cases and tests`.
- Đã push thành công lên `origin/main`.
- Các thay đổi Bài 8 không được đưa vào commit này.

## 3. Luồng xử lý có thể tái hiện

```text
Đọc từng file dirty
  → Kiểm tra REQUIRED
      → Thiếu cột: ValueError, dừng lần chạy
      → Đủ cột: duyệt từng dòng
          → Tìm các trường thiếu trong REQUIRED_VALUES
          → Tính score, errors và missing_cols
  → Tổng hợp số dòng thiếu giá trị
  → Ghi 10 dòng đầu mỗi bảng vào 07-schema.txt
```

Việc kiểm tra cấu trúc trước giúp tránh truy cập một cột không tồn tại khi chấm điểm. Giữ danh sách trường thiếu giúp người đọc xác định nguyên nhân cụ thể của điểm thấp. Kiểm thử các dạng NULL, bảng rỗng và số 0 giúp xác minh các tình huống mà dữ liệu mẫu chưa bao phủ đầy đủ.

## 4. Cách chạy lại trong PowerShell

Chạy tại thư mục gốc dự án. Các lệnh dưới đây sử dụng đúng bản Python và thư mục dependency đã dùng trong lần xác minh thành công:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) '.test-deps')
$env:PYTHONIOENCODING = 'utf-8'
$schemaPython = 'C:/Users/MSI/AppData/Local/Programs/Python/Python311/python.exe'

& $schemaPython -m pytest tests/test_schema_validator.py tests/test_validators_public.py -q
& $schemaPython -m src.validators.schema_validator
```

Lệnh thứ hai ghi lại `docs/evidence/07-schema.txt`. Khi dùng môi trường Python khác, cần cài pandas và pytest tương ứng.

## 5. Các file để đối chiếu

- Đề bài: `assignments/MD01-B7_Bai_tap_DATA_CLEANING_DATA_QUALITY.md`.
- Quy định dữ liệu: `docs/data_contract.md`.
- Mã xử lý: `src/validators/schema_validator.py`.
- Kiểm thử bổ sung: `tests/test_schema_validator.py`.
- Kiểm thử công khai: `tests/test_validators_public.py`.
- Minh chứng: `docs/evidence/07-schema.txt`.

Tài liệu này được tạo sau commit `18772b0`; bản thân tài liệu chưa được commit hoặc push trong bước tạo tài liệu.
