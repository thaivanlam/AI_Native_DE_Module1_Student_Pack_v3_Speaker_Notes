# Bài tập: DATA CLEANING & DATA QUALITY

## Mục tiêu

- Xây dựng bộ lọc kiểm định chất lượng dữ liệu (**Data Quality Firewall**) đa tầng: Schema, Business Rules và Cross-Table Integrity.
- Phân loại và tách tập dữ liệu thành 2 luồng: hợp lệ (`valid`) và vi phạm (`rejected`) kèm mã định danh lỗi (`error_code`).
- Xây dựng báo cáo Data Quality và kiểm tra nguyên tắc bảo toàn dữ liệu: **Input = Valid + Rejected**.

## Nội dung 4 bài tập thực hành

Kiểm thử trên tập dữ liệu bẩn: `data/dirty/day_2026-07-02/`

---

### Bài 1: Schema & Completeness Validation

**File:** `src/validators/schema_validator.py`

**Yêu cầu:**

1. Kiểm tra danh sách cột bắt buộc (`REQUIRED`) theo Data Contract của 5 bảng: `customers`, `products`, `orders`, `order_items`, `payments`. Nếu thiếu cột cấu trúc → báo lỗi `ValueError`.
2. Kiểm tra missing value (NULL hoặc chuỗi rỗng) ở các trường bắt buộc (`REQUIRED_VALUES`).
3. Tính điểm chất lượng từng dòng (row scoring): tỷ lệ các trường hợp lệ (0-100%).

**Kết quả cần đạt:** Chạy trên file dirty ra danh sách cột thiếu (nếu có) và điểm số + lỗi của từng dòng.

**Minh chứng nộp:**

- Code: `src/validators/schema_validator.py`
- Log 10 dòng đầu kèm score: `docs/evidence/07-schema.txt`
  - Mẫu: `row_id=CUS005 score=75 errors=[MISSING_REQUIRED]`

---

### Bài 2: Business Rules Validation

**File:** `src/validators/business_validator.py`

**Yêu cầu:** Hoàn thiện hàm `split_valid_invalid(name, df)` kiểm tra các quy tắc cấp dòng (row-level rules):

1. **Email:** Regex `r'^[^@\s]+@[^@\s]+\.[^@\s]+$'` → `INVALID_EMAIL`.
2. **Enum:** Giá trị `status`, `channel`, `payment_method`, `payment_status` phải thuộc danh sách cho phép → `INVALID_<COL>`.
3. **Range:** `unit_price >= 0`, `quantity > 0`, `order_total >= 0`, `amount >= 0`, `discount_amount >= 0`.
4. **Consistency:** `discount_amount <= quantity * unit_price` → `DISCOUNT_EXCEEDS_GROSS`.
5. Nếu dòng có nhiều lỗi, nối các mã lỗi bằng ký tự `|` (ví dụ: `INVALID_EMAIL|INVALID_STATUS`).

**Kết quả cần đạt:** Tách DataFrame thành `(valid_df, rejected_df)`. Bảng `rejected` có thêm cột `error_code`.

**Minh chứng nộp:**

- Code: `src/validators/business_validator.py`
- Bảng đếm vi phạm per-rule: `docs/evidence/07-business.txt`
  - Mẫu: `INVALID_EMAIL: 12, NEGATIVE_PRICE: 5, ...`

---

### Bài 3: Cross-Table Integrity & Chronology

**File:** `src/validators/integrity_validator.py`

**Yêu cầu:** Hoàn thiện hàm `split_cross_table_invalid(name, df)`:

1. **Foreign Key Checks (4 cặp):**
   - `products.category_id` → `categories.category_id` (`FK_CATEGORY_NOT_FOUND`)
   - `orders.customer_id` → `customers.customer_id` (`FK_CUSTOMER_NOT_FOUND`)
   - `order_items.order_id` → `orders.order_id` & `order_items.product_id` → `products.product_id`
   - `payments.order_id` → `orders.order_id`
2. **Chronology Check:**
   - `payments.payment_date >= orders.order_date`. Nếu vi phạm → `PAYMENT_BEFORE_ORDER`.

**Kết quả cần đạt:** Lọc và tách toàn bộ các orphan rows hoặc thanh toán trước ngày đặt hàng vào danh sách reject.

**Minh chứng nộp:**

- Code: `src/validators/integrity_validator.py`
- Danh sách vi phạm: `docs/evidence/07-integrity.txt`
  - Mẫu: `order_items id=ITM999 order_id=ORD8888 NOT FOUND (FK_ORDER_NOT_FOUND)`

---

### Bài 4: Data Quality Report & Invariant Reconciliation

**File:** `src/quality_report.py`

**Yêu cầu:**

1. Tổng hợp các chỉ số: `dataset`, `input`, `valid`, `rejected`.
2. Xuất báo cáo ra file `reports/data_quality_report.csv` và `reports/data_quality_summary.json`.
3. Kiểm tra nguyên tắc bất biến (Invariant):

   ```
   Input = Valid + Rejected
   ```

   Pipeline phải dùng lệnh `assert` để đảm bảo đẳng thức này luôn đúng với mọi dataset.

**Kết quả cần đạt:** File CSV đầy đủ dữ liệu, lệnh `assert` chạy qua không văng lỗi.

**Minh chứng nộp:**

- Code: `src/quality_report.py`
- File báo cáo: `reports/data_quality_report.csv`
- Log xác nhận invariant: `docs/evidence/07-invariant.txt`
  - Mẫu: `customers: 40 = 36 + 4 OK`

---

## Danh mục nộp bài

| Bài tập | Minh chứng phải có | Đường dẫn file |
|---|---|---|
| Bài 1: Schema | Code + Log chấm điểm row score mẫu | `src/validators/schema_validator.py`<br>`docs/evidence/07-schema.txt` |
| Bài 2: Business | Code + Bảng đếm vi phạm per-rule | `src/validators/business_validator.py`<br>`docs/evidence/07-business.txt` |
| Bài 3: Integrity | Code + Danh sách orphan FK & chronology | `src/validators/integrity_validator.py`<br>`docs/evidence/07-integrity.txt` |
| Bài 4: Report | Code + CSV report + Log invariant `Input = Valid + Rejected` | `src/quality_report.py`<br>`reports/data_quality_report.csv`<br>`docs/evidence/07-invariant.txt` |
