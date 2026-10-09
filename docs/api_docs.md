# Tài liệu kỹ thuật: E-commerce Training Mock API

Tài liệu mô tả REST API nguồn dùng cho pipeline Data Ingestion (Bài 1). Các mã trạng thái, tham số và số liệu ghi ở đây đều đã được gọi thử thật, minh chứng nằm trong [evidence/06-explore-log.txt](evidence/06-explore-log.txt) (sinh bởi `scripts/explore_api.py`). Riêng thứ tự kiểm tra lỗi (mục 6) và các ghi chú ở mục 7 được rút ra từ việc đọc mã nguồn `mock_api/app.py`.

## 1. Tổng quan

| Mục | Giá trị |
|---|---|
| Base URL | `http://localhost:8000` (cấu hình qua biến môi trường `MOCK_API_URL`) |
| Giao thức | HTTP, chỉ hỗ trợ `GET` (API chỉ đọc) |
| Định dạng phản hồi | JSON, UTF-8 |
| Xác thực | Header `X-API-Key` |
| Phân trang | Theo số trang: `page` + `page_size` |
| Lọc gia tăng | `updated_after` (ISO 8601, có múi giờ) |
| Phiên bản | 1.0 (FastAPI, mã nguồn: `mock_api/app.py`) |

Khởi động API:

```bash
docker compose up -d mock-api
# hoặc chạy trực tiếp không cần Docker:
python -m uvicorn app:app --app-dir mock_api --port 8000
```

## 2. Xác thực (Authentication)

| Header | Bắt buộc | Giá trị |
|---|---|---|
| `X-API-Key` | Có, với mọi endpoint trừ `/health` | `******` |

- Secret được cấu hình qua biến môi trường `MOCK_API_KEY` (đặt trong file `.env`, xem mẫu ở `.env.example`). Code đọc qua `SETTINGS.api_key` trong `src/config.py`, không hard-code trong mã nguồn pipeline.
- File `.env` đã nằm trong `.gitignore` nên không bị commit.
- Trong log và tài liệu, key luôn được thay bằng `******`.
- Key chỉ được chấp nhận qua header. Truyền key qua query string (`?api_key=...`) vẫn nhận `401`.

| Tình huống | Kết quả |
|---|---|
| Header `X-API-Key` đúng | `200 OK` |
| Key sai | `401 Unauthorized`, body `{"detail": "Invalid API key"}` |
| Thiếu header | `401 Unauthorized`, body `{"detail": "Invalid API key"}` |

Ví dụ gọi (key lấy từ biến môi trường, không gõ trực tiếp vào lệnh):

```bash
curl -H "X-API-Key: $MOCK_API_KEY" "http://localhost:8000/orders?page=1&page_size=10"
```

## 3. Endpoints

### 3.1. `GET /health`

Kiểm tra API còn sống. Không cần xác thực, không có tham số.

```json
{"status": "ok"}
```

### 3.2. Năm endpoint nghiệp vụ

Cả 5 endpoint dùng chung tham số, cấu trúc phản hồi và mã lỗi (mục 4, 5, 6).

| Endpoint | Khóa chính | Tổng số dòng | Số trang (`page_size=100`) | Bảng đích |
|---|---|---|---|---|
| `GET /customers` | `customer_id` | 100 | 1 | `core.customers` |
| `GET /products` | `product_id` | 50 | 1 | `core.products` |
| `GET /orders` | `order_id` | 600 | 6 | `core.orders` |
| `GET /order-items` | `order_item_id` | 1533 | 16 | `core.order_items` |
| `GET /payments` | `payment_id` | 536 | 6 | `core.payments` |

> **Lưu ý:** đường dẫn là `/order-items` (gạch ngang), trong khi bảng đích là `order_items` (gạch dưới). Gọi `/order_items` trả về `404 Not Found`.

Khóa chính của cả 5 resource đều duy nhất trên toàn bộ dữ liệu (đã kiểm tra bằng full load).

## 4. Tham số truy vấn (Query Parameters)

| Tham số | Kiểu | Bắt buộc | Mặc định | Ràng buộc | Mô tả |
|---|---|---|---|---|---|
| `page` | integer | Không | `1` | `>= 1` | Số thứ tự trang, bắt đầu từ 1 |
| `page_size` | integer | Không | `100` | `1` đến `500` | Số bản ghi mỗi trang |
| `updated_after` | string | Không | (không lọc) | ISO 8601, có múi giờ | Chỉ trả bản ghi có `updated_at` **lớn hơn** mốc này |

### Phân trang

- Bản ghi của trang `page` là đoạn từ vị trí `(page - 1) * page_size` trong tập kết quả.
- `has_next = true` khi còn dữ liệu ở trang sau. Đây là điều kiện dừng vòng lặp phân trang: dừng khi `has_next = false`.
- Gọi vượt trang cuối không báo lỗi: trả `200` với `data: []` và `has_next: false`.
- `total` là số bản ghi **sau khi áp dụng bộ lọc** `updated_after`, không phải tổng số bản ghi của resource.
- API không có tham số sắp xếp; bản ghi trả theo thứ tự cố định của nguồn.

### Lọc gia tăng với `updated_after`

- So sánh là **lớn hơn nghiêm ngặt** (`updated_at > updated_after`). Bản ghi có `updated_at` đúng bằng mốc sẽ không được trả về. Ví dụ: truyền mốc bằng `max(updated_at)` của `/orders` cho `total = 0`.
- So sánh theo thời điểm thực, không theo chuỗi: `2026-07-01T12:00:00Z` và `2026-07-01T19:00:00+07:00` cho cùng kết quả (234/600 orders).
- Hậu tố `Z` được chấp nhận và hiểu là UTC.
- **Phải URL-encode giá trị.** Dấu `+` trong offset `+07:00` nếu không encode thành `%2B` sẽ bị đọc thành khoảng trắng và nhận lỗi `400`. Thư viện `requests` tự encode khi truyền qua `params={...}`; chỉ gặp lỗi này khi tự ghép chuỗi URL.
- **Phải có múi giờ.** Giá trị không có múi giờ (`2026-07-01T12:00:00` hoặc `2026-07-01`) làm server trả `500 Internal Server Error` thay vì `400` (xem mục 6).

## 5. Cấu trúc JSON phản hồi

### 5.1. Vỏ phân trang (dùng chung cho 5 endpoint)

| Trường | Kiểu | Mô tả |
|---|---|---|
| `page` | integer | Trang hiện tại (lặp lại giá trị request) |
| `page_size` | integer | Kích thước trang (lặp lại giá trị request) |
| `total` | integer | Tổng số bản ghi khớp bộ lọc |
| `has_next` | boolean | Còn trang kế tiếp hay không |
| `data` | array | Danh sách bản ghi của trang |

Ví dụ `GET /orders?page=1&page_size=1`:

```json
{
  "page": 1,
  "page_size": 1,
  "total": 600,
  "has_next": true,
  "data": [
    {
      "order_id": "ORD005001",
      "customer_id": "CUS000834",
      "order_date": "2026-07-01T18:57:00+07:00",
      "status": "completed",
      "shipping_city": "Bac Ninh",
      "channel": "mobile_app",
      "order_total": "19156500.00",
      "source_system": "ecommerce_api",
      "created_at": "2026-07-01T18:57:00+07:00",
      "updated_at": "2026-07-01T20:41:00+07:00"
    }
  ]
}
```

### 5.2. Quy ước kiểu dữ liệu

- **Số tiền** (`unit_price`, `cost_price`, `order_total`, `discount_amount`, `amount`) trả về dạng **chuỗi** có 2 chữ số thập phân (ví dụ `"19156500.00"`), cần ép sang `NUMERIC` khi nạp.
- **Thời gian** là chuỗi ISO 8601 có offset `+07:00`.
- `quantity` là trường số nguyên duy nhất; các trường còn lại đều là chuỗi.
- Trong dữ liệu hiện tại không có trường nào `null`, và mọi bản ghi của cùng một resource có cùng tập trường.

### 5.3. Trường của từng resource

**`/customers`** (10 trường)

| Trường | Kiểu JSON | Ví dụ |
|---|---|---|
| `customer_id` | string | `CUS000001` |
| `full_name` | string | `Glenda Crosby` |
| `email` | string | `user0001@example.com` |
| `phone` | string | `0955750088` |
| `city` | string | `Can Tho` |
| `customer_segment` | string | `Gold` |
| `status` | string | `active` |
| `source_system` | string | `daily_file` |
| `created_at` | string (ISO 8601) | `2025-11-05T15:02:00+07:00` |
| `updated_at` | string (ISO 8601) | `2026-07-01T08:01:00+07:00` |

**`/products`** (9 trường)

| Trường | Kiểu JSON | Ví dụ |
|---|---|---|
| `product_id` | string | `PRD000001` |
| `category_id` | string | `CAT018` |
| `product_name` | string | `Product 001 Note` |
| `unit_price` | string (số thập phân) | `1039500.00` |
| `cost_price` | string (số thập phân) | `700000.00` |
| `status` | string | `active` |
| `source_system` | string | `daily_file` |
| `created_at` | string (ISO 8601) | `2025-09-17T08:00:00+07:00` |
| `updated_at` | string (ISO 8601) | `2026-07-01T08:01:00+07:00` |

**`/orders`** (10 trường)

| Trường | Kiểu JSON | Ví dụ |
|---|---|---|
| `order_id` | string | `ORD005001` |
| `customer_id` | string | `CUS000834` |
| `order_date` | string (ISO 8601) | `2026-07-01T18:57:00+07:00` |
| `status` | string | `completed` |
| `shipping_city` | string | `Bac Ninh` |
| `channel` | string | `mobile_app` |
| `order_total` | string (số thập phân) | `19156500.00` |
| `source_system` | string | `ecommerce_api` |
| `created_at` | string (ISO 8601) | `2026-07-01T18:57:00+07:00` |
| `updated_at` | string (ISO 8601) | `2026-07-01T20:41:00+07:00` |

**`/order-items`** (9 trường)

| Trường | Kiểu JSON | Ví dụ |
|---|---|---|
| `order_item_id` | string | `ITM00012718` |
| `order_id` | string | `ORD005001` |
| `product_id` | string | `PRD000343` |
| `quantity` | integer | `1` |
| `unit_price` | string (số thập phân) | `6980000.00` |
| `discount_amount` | string (số thập phân) | `0.00` |
| `source_system` | string | `ecommerce_api` |
| `created_at` | string (ISO 8601) | `2026-07-01T18:57:00+07:00` |
| `updated_at` | string (ISO 8601) | `2026-07-01T18:57:00+07:00` |

**`/payments`** (9 trường)

| Trường | Kiểu JSON | Ví dụ |
|---|---|---|
| `payment_id` | string | `PAY004518` |
| `order_id` | string | `ORD005001` |
| `payment_date` | string (ISO 8601) | `2026-07-01T23:35:00+07:00` |
| `payment_method` | string | `bank_transfer` |
| `payment_status` | string | `success` |
| `amount` | string (số thập phân) | `19156500.00` |
| `source_system` | string | `ecommerce_api` |
| `created_at` | string (ISO 8601) | `2026-07-01T23:35:00+07:00` |
| `updated_at` | string (ISO 8601) | `2026-07-01T23:35:00+07:00` |

### 5.4. Khoảng `updated_at` của dữ liệu hiện có

| Resource | Nhỏ nhất | Lớn nhất |
|---|---|---|
| `/customers` | `2026-07-01T08:01:00+07:00` | `2026-07-01T09:59:00+07:00` |
| `/products` | `2026-07-01T08:01:00+07:00` | `2026-07-01T10:40:00+07:00` |
| `/orders` | `2026-07-01T08:12:00+07:00` | `2026-07-02T01:44:00+07:00` |
| `/order-items` | `2026-07-01T08:01:00+07:00` | `2026-07-01T22:59:00+07:00` |
| `/payments` | `2026-07-01T08:47:00+07:00` | `2026-07-02T03:22:00+07:00` |

## 6. Mã trạng thái & lỗi

| Mã | Khi nào | Body | Nên retry? |
|---|---|---|---|
| `200 OK` | Request hợp lệ (kể cả trang rỗng vượt trang cuối) | Vỏ phân trang ở mục 5.1 | — |
| `400 Bad Request` | `updated_after` không parse được theo ISO 8601 | `{"detail": "updated_after must be ISO 8601"}` | Không, sửa tham số |
| `401 Unauthorized` | Thiếu hoặc sai `X-API-Key` | `{"detail": "Invalid API key"}` | Không, kiểm tra `MOCK_API_KEY` |

Ngoài 3 mã chính trên, khi gọi thử còn gặp:

| Mã | Khi nào | Body |
|---|---|---|
| `404 Not Found` | Sai đường dẫn, ví dụ `/order_items` | `{"detail": "Not Found"}` |
| `422 Unprocessable Entity` | `page < 1`, `page_size` ngoài `1..500`, hoặc không phải số nguyên | `{"detail": [{"loc": ["query", "page_size"], "msg": "Input should be less than or equal to 500", ...}]}` |
| `500 Internal Server Error` | `updated_after` đúng cú pháp ISO 8601 nhưng không có múi giờ | `Internal Server Error` (text thuần, không phải JSON) |

Lỗi `500` ở trên là một hạn chế của mock API: server so sánh thời điểm không múi giờ với `updated_at` có múi giờ và bị lỗi nội bộ. Về phía client, đây là lỗi do tham số nên retry không giúp gì; cách tránh là luôn gửi `updated_after` kèm múi giờ.

Thứ tự kiểm tra của server: tham số `page`/`page_size` (422) → API key (401) → `updated_after` (400).

## 7. Ghi chú cho việc xây dựng pipeline

- Đặt `timeout` cho mọi request; API không có rate limit nhưng có thể không phản hồi khi container dừng.
- Chỉ retry với lỗi mạng và lỗi `5xx` tạm thời. Lỗi `400`, `401`, `404`, `422` là lỗi cấu hình hoặc tham số, retry sẽ cho cùng kết quả.
- Vì `updated_after` so sánh `>` nghiêm ngặt, dùng `max(updated_at)` của lần chạy trước làm watermark sẽ không lấy lặp lại bản ghi ở đúng mốc đó.
- Dữ liệu phía server không đổi trong lúc phân trang, nên duyệt theo `page` không bị sót hay trùng bản ghi.
- Full load một resource tốn ít request nhất với `page_size=500` (ví dụ `/order-items`: 4 request thay vì 16).
