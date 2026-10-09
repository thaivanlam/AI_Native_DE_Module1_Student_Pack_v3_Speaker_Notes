"""Khám phá Mock REST API (Bài 1): health, auth, pagination, filtering, 5 endpoints.

Chạy: python scripts/explore_api.py > docs/evidence/06-explore-log.txt
API key chỉ đọc từ SETTINGS (biến môi trường MOCK_API_KEY) và luôn được in ở dạng ******.
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import SETTINGS

TIMEOUT = 10
MASK = "******"
RESOURCES = {
    "/customers": "customer_id",
    "/products": "product_id",
    "/orders": "order_id",
    "/order-items": "order_item_id",
    "/payments": "payment_id",
}
failures = []


def call(path: str, params: dict | None = None, key: str | None = "valid") -> requests.Response:
    """key: 'valid' = key từ SETTINGS, None = không gửi header, giá trị khác = key sai."""
    headers = {}
    if key == "valid":
        headers["X-API-Key"] = SETTINGS.api_key
    elif key is not None:
        headers["X-API-Key"] = key
    response = requests.get(SETTINGS.api_url + path, params=params, headers=headers, timeout=TIMEOUT)
    shown = response.request.path_url
    auth = f"X-API-Key: {MASK} ({'key dung' if key == 'valid' else 'key sai'})" if headers else "(khong gui X-API-Key)"
    print(f"GET {shown}  [{auth}]")
    return response


def check(label: str, ok: bool) -> None:
    print(f"   [{'OK' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def show(response: requests.Response) -> None:
    body = response.text if len(response.text) <= 200 else response.text[:200] + "..."
    print(f"   -> {response.status_code} {response.reason} | {body}")


def show_page(response: requests.Response) -> dict:
    payload = response.json()
    print(
        f"   -> {response.status_code} {response.reason} | page={payload['page']} "
        f"page_size={payload['page_size']} total={payload['total']} "
        f"has_next={str(payload['has_next']).lower()} len(data)={len(payload['data'])}"
    )
    return payload


def fetch_all(path: str) -> list:
    rows, page = [], 1
    while True:
        payload = requests.get(
            SETTINGS.api_url + path,
            params={"page": page, "page_size": 500},
            headers={"X-API-Key": SETTINGS.api_key},
            timeout=TIMEOUT,
        ).json()
        rows.extend(payload["data"])
        if not payload["has_next"]:
            return rows
        page += 1


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> int:
    print("# 06-explore-log — Minh chung kham pha Mock REST API (Bai 1)")
    print(f"# Ngay chay: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"# Base URL: {SETTINGS.api_url}")
    source = "bien moi truong / .env" if os.getenv("MOCK_API_KEY") else "gia tri mac dinh trong src/config.py"
    print(f"# MOCK_API_KEY={MASK} (len={len(SETTINGS.api_key)}, nguon: {source})")

    print("\n== 1. Health check")
    r = call("/health", key=None)
    show(r)
    check("status 200 va body {'status': 'ok'}", r.status_code == 200 and r.json() == {"status": "ok"})

    print("\n== 2. Authentication (header X-API-Key)")
    r = call("/orders", {"page": 1, "page_size": 1})
    show_page(r)
    check("key dung -> 200", r.status_code == 200)
    r = call("/orders", {"page": 1, "page_size": 1}, key="wrong-key")
    show(r)
    check("key sai -> 401 Invalid API key", r.status_code == 401 and r.json() == {"detail": "Invalid API key"})
    r = call("/orders", {"page": 1, "page_size": 1}, key=None)
    show(r)
    check("thieu header -> 401 Invalid API key", r.status_code == 401 and r.json() == {"detail": "Invalid API key"})
    r = requests.get(
        SETTINGS.api_url + "/orders",
        params={"page": 1, "page_size": 1, "api_key": SETTINGS.api_key},
        timeout=TIMEOUT,
    )
    print(f"GET /orders?page=1&page_size=1&api_key={MASK}  [(khong gui X-API-Key)]")
    show(r)
    check("key truyen qua query string khong duoc chap nhan -> 401", r.status_code == 401)

    print("\n== 3. Pagination (page >= 1, page_size 1..500, mac dinh 100)")
    first = show_page(call("/orders", {"page": 1, "page_size": 10}))
    check(
        "metadata gom dung 5 khoa: page, page_size, total, has_next, data",
        sorted(first) == ["data", "has_next", "page", "page_size", "total"],
    )
    check("page 1: 10 dong, has_next=true", len(first["data"]) == 10 and first["has_next"] is True)
    total = first["total"]
    default = show_page(call("/orders"))
    check("khong truyen tham so -> page=1, page_size=100", (default["page"], default["page_size"]) == (1, 100))
    last_page = -(-total // 100)
    last = show_page(call("/orders", {"page": last_page, "page_size": 100}))
    check(f"trang cuoi ({last_page}) -> has_next=false", last["has_next"] is False and len(last["data"]) > 0)
    beyond = show_page(call("/orders", {"page": last_page + 1, "page_size": 100}))
    check("vuot trang cuoi -> 200, data=[], has_next=false", beyond["data"] == [] and beyond["has_next"] is False)
    biggest = show_page(call("/orders", {"page": 1, "page_size": 500}))
    check("page_size=500 (toi da) -> 200", len(biggest["data"]) == min(500, total))
    for params in ({"page": 0}, {"page_size": 0}, {"page_size": 501}, {"page": "abc"}):
        r = call("/orders", params)
        detail = r.json()["detail"][0]
        print(f"   -> {r.status_code} {r.reason} | loc={detail['loc']} msg={detail['msg']}")
        check(f"{params} ngoai mien gia tri -> 422", r.status_code == 422)

    print("\n== 4. Filtering (updated_after, ISO 8601)")
    orders = fetch_all("/orders")
    cutoff = "2026-07-01T12:00:00Z"
    filtered = show_page(call("/orders", {"updated_after": cutoff, "page_size": 10}))
    expected = sum(parse_ts(o["updated_at"]) > parse_ts(cutoff) for o in orders)
    check(f"total khop voi so dong updated_at > cutoff tinh lai tu full load ({expected}/{len(orders)})",
          filtered["total"] == expected)
    boundary = max(o["updated_at"] for o in orders)
    edge = show_page(call("/orders", {"updated_after": boundary}))
    check("cutoff = max(updated_at) -> total=0 (so sanh > nghiem ngat, khong phai >=)", edge["total"] == 0)
    same_instant = show_page(call("/orders", {"updated_after": "2026-07-01T19:00:00+07:00", "page_size": 10}))
    check("offset +07:00 (da URL-encode %2B) cho cung ket qua voi 12:00:00Z", same_instant["total"] == filtered["total"])
    r = call("/orders", {"updated_after": "not-a-date"})
    show(r)
    check(
        "sai dinh dang -> 400 updated_after must be ISO 8601",
        r.status_code == 400 and r.json() == {"detail": "updated_after must be ISO 8601"},
    )
    r = requests.get(
        SETTINGS.api_url + "/orders?updated_after=2026-07-01T19:00:00+07:00",
        headers={"X-API-Key": SETTINGS.api_key},
        timeout=TIMEOUT,
    )
    print(f"GET {r.request.path_url}  [X-API-Key: {MASK}]")
    show(r)
    check("dau '+' khong URL-encode bi doc thanh khoang trang -> 400", r.status_code == 400)
    for naive in ("2026-07-01T12:00:00", "2026-07-01"):
        r = call("/orders", {"updated_after": naive})
        show(r)
        check(f"'{naive}' khong co mui gio -> 500 (loi phia server)", r.status_code == 500)

    print("\n== 5. Khao sat 5 endpoints nghiep vu")
    for path, pk in RESOURCES.items():
        payload = show_page(call(path, {"page": 1, "page_size": 100}))
        rows = fetch_all(path)
        ids = [row[pk] for row in rows]
        stamps = [row["updated_at"] for row in rows]
        print(f"   fields({len(rows[0])}): {', '.join(rows[0])}")
        print(f"   updated_at: {min(stamps)} .. {max(stamps)} | so trang voi page_size=100: {-(-len(rows) // 100)}")
        check(
            f"{path}: full load {len(rows)} dong = total, {pk} duy nhat",
            len(rows) == payload["total"] and len(set(ids)) == len(ids),
        )
    r = call("/order_items")
    show(r)
    check("/order_items (gach duoi) khong ton tai -> 404", r.status_code == 404)

    print("\n== Tong ket")
    print(
        f"GET /health -> 200 ok | sai key -> 401 Invalid API key | "
        f"/orders?page=1&page_size=10 -> {len(first['data'])} rows "
        f"has_next={str(first['has_next']).lower()} total={total}"
    )
    print(f"checks failed: {len(failures)}")
    print(f"\nexit code: {1 if failures else 0}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
