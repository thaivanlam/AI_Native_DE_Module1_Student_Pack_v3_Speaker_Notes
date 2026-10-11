"""Demo phân trang + lưu RAW của src/api_client.py và src/pipeline.py (Bài 3).

Chạy: python scripts/demo_fetch.py > docs/evidence/06-fetch-log.txt 2>&1
Mỗi lần chạy tạo một thư mục data/raw/<run_id>/ mới, không đụng tới các run cũ.
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api_client import MASK, fetch_all_pages
from src.config import SETTINGS
from src.pipeline import API_RESOURCES, extract_api_to_raw, new_run_id, save_raw
from src.transform import normalize
from src.extract_files import read_dataset

PRIMARY_KEYS = {
    "customers": "customer_id",
    "products": "product_id",
    "orders": "order_id",
    "order_items": "order_item_id",
    "payments": "payment_id",
}
failures = []


def say(text: str = "") -> None:
    print(text, flush=True)


def check(label: str, ok: bool) -> None:
    say(f"[{'OK' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def api_total(resource: str) -> int:
    response = requests.get(
        f"{SETTINGS.api_url}/{resource.replace('_', '-')}",
        params={"page": 1, "page_size": 1},
        headers={"X-API-Key": SETTINGS.api_key},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["total"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(SETTINGS.root).as_posix()


def main() -> int:
    run_id = new_run_id()
    say("# 06-fetch-log — Minh chung phan trang + luu RAW (Bai 3)")
    say(f"# Ngay chay: {datetime.now():%Y-%m-%d %H:%M:%S}")
    say(f"# Base URL: {SETTINGS.api_url} | X-API-Key: {MASK} | page_size=100 | run_id={run_id}")

    say("\n== 1. Full load 5 resource: API -> data/raw/<run_id>/<resource>.json")
    say(f"extract_api_to_raw(run_id='{run_id}')  # tuong duong CLI: python -m src.pipeline --run-id {run_id}")
    raw_files = extract_api_to_raw(run_id=run_id)

    say("\n== 2. Doi soat file RAW voi API")
    for resource in API_RESOURCES:
        path = raw_files[resource]
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["data"]
        ids = {row[PRIMARY_KEYS[resource]] for row in rows}
        total = api_total(resource)
        say(f"{rel(path)} | rows={len(rows)} api_total={total} unique_pk={len(ids)} "
            f"pages={-(-total // 100)} bytes={path.stat().st_size}")
        check(
            f"{resource}: du 100% ban ghi, khong sot trang, khong trung khoa",
            len(rows) == total == len(ids) == payload["total"],
        )
    orders_path = raw_files["orders"]
    first = json.loads(orders_path.read_text(encoding="utf-8"))["data"][0]
    say(f"ban ghi dau trong RAW orders: {json.dumps(first, ensure_ascii=False)}")
    check(
        "RAW giu nguyen kieu du lieu goc cua API (so tien van la chuoi, chua chuan hoa)",
        isinstance(first["order_total"], str) and first["updated_at"].endswith("+07:00"),
    )

    say("\n== 3. RAW Immutability")
    before = {resource: sha256(path) for resource, path in raw_files.items()}
    try:
        save_raw("orders", [{"order_id": "OVERWRITE"}], run_id)
        say("-> ghi de thanh cong (SAI)")
        refused = False
    except FileExistsError as exc:
        say(f"save_raw('orders', ..., run_id='{run_id}') lan 2 -> FileExistsError: {exc.strerror}")
        refused = True
    check("khong ghi de duoc file RAW cua run da ton tai", refused)
    clean = normalize(read_dataset(orders_path))
    say(f"normalize(read_dataset(orders.json)) -> rows={len(clean)} "
        f"order_total dtype={clean['order_total'].dtype} updated_at dtype={clean['updated_at'].dtype}")
    after = {resource: sha256(path) for resource, path in raw_files.items()}
    say(f"sha256 orders.json truoc/sau buoc doc + normalize: {before['orders'][:16]}... / {after['orders'][:16]}...")
    check("5 file RAW khong doi (sha256) sau khi doc va chuan hoa", before == after)

    say("\n== 4. Incremental: updated_after duoc truyen qua moi trang")
    cutoff = "2026-07-01T12:00:00Z"
    say(f"fetch_all_pages('orders', updated_after='{cutoff}')")
    incremental = fetch_all_pages("orders", updated_after=cutoff)
    expected = sum(
        datetime.fromisoformat(row["updated_at"]) > datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        for row in json.loads(orders_path.read_text(encoding="utf-8"))["data"]
    )
    check(
        f"so dong incremental ({len(incremental)}) khop voi so dong updated_at > cutoff trong RAW ({expected})",
        len(incremental) == expected and 0 < expected < 600,
    )

    say("\n== Tong ket")
    say(f"resource=orders page=1 rows=100 ... page=6 rows=100 total_so_far=600 | RAW saved to {rel(orders_path)}")
    say(f"checks failed: {len(failures)}")
    say(f"\nexit code: {1 if failures else 0}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
