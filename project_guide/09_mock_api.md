# 9. Mock REST API

← [8. Python pipeline](08_python_pipeline.md) · Tiếp: [10. Vận hành](10_van_hanh.md) →

Nguồn: [mock_api/app.py](../mock_api/app.py) · Dữ liệu: `mock_api/data/*.json` · Container: `ecommerce-mock-api`

## 9.1 Mục đích

Giả lập một hệ thống nguồn dạng REST để luyện kỹ năng ingestion thực tế: xác thực bằng API key, phân trang, lọc incremental theo thời gian, xử lý lỗi HTTP.

## 9.2 Endpoint

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| GET | `/health` | Không | Trả `{"status": "ok"}` |
| GET | `/customers` | `X-API-Key` | Danh sách khách hàng |
| GET | `/products` | `X-API-Key` | Danh sách sản phẩm |
| GET | `/orders` | `X-API-Key` | Danh sách đơn hàng |
| GET | `/order-items` | `X-API-Key` | Danh sách dòng hàng |
| GET | `/payments` | `X-API-Key` | Danh sách thanh toán |

Swagger UI: `http://localhost:8000/docs`.

## 9.3 Tham số truy vấn

| Tham số | Kiểu | Mặc định | Ràng buộc | Ý nghĩa |
|---|---|---|---|---|
| `page` | int | 1 | ≥ 1 | Trang cần lấy |
| `page_size` | int | 100 | 1–500 | Số bản ghi mỗi trang |
| `updated_after` | string | — | ISO 8601 | Chỉ trả bản ghi có `updated_at` (hoặc `created_at` nếu thiếu) **lớn hơn** mốc này |

## 9.4 Response

```json
{
  "page": 1,
  "page_size": 50,
  "total": 600,
  "has_next": true,
  "data": [ { "order_id": "ORD005001", "...": "..." } ]
}
```

- `total` là tổng số bản ghi **sau khi** lọc `updated_after`.
- Lặp `page += 1` cho tới khi `has_next = false`.

## 9.5 Lỗi

| HTTP | Khi nào |
|---|---|
| 401 `Invalid API key` | Thiếu hoặc sai header `X-API-Key` |
| 400 `updated_after must be ISO 8601` | `updated_after` không parse được |
| 422 | `page`/`page_size` ngoài khoảng cho phép (FastAPI validate) |

## 9.6 Cách hoạt động bên trong

- Mỗi request đọc lại file JSON tương ứng từ `mock_api/data/` (mount read-only).
- Lọc `updated_after` bằng `datetime.fromisoformat`, hỗ trợ hậu tố `Z`.
- Phân trang bằng slicing `rows[start:end]`.
- API key lấy từ biến môi trường `API_KEY` (compose truyền từ `MOCK_API_KEY`, mặc định `training-key`).

## 9.7 Ví dụ gọi

```bash
docker compose up -d mock-api
curl http://localhost:8000/health
curl -H "X-API-Key: training-key" \
  "http://localhost:8000/orders?page=1&page_size=50&updated_after=2026-07-01T00:00:00Z"
```

```python
import requests
r = requests.get(
    "http://localhost:8000/orders",
    headers={"X-API-Key": "training-key"},
    params={"page": 1, "page_size": 100, "updated_after": "2026-07-01T00:00:00Z"},
    timeout=10,
)
r.raise_for_status()
body = r.json()
```
