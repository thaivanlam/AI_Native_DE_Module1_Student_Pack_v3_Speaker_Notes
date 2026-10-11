"""Buổi 6: API -> RAW -> CORE. Payload thô được lưu vào data/raw/<run_id>/ trước mọi bước transform."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from src.api_client import fetch_all_pages
from src.config import SETTINGS
from src.extract_files import read_dataset
from src.load_postgres import upsert_dataframe
from src.logger import get_logger
from src.transform import normalize

log = get_logger("pipeline")

# Thứ tự theo phụ thuộc khóa ngoại: bảng cha trước, bảng con sau.
API_RESOURCES = ("customers", "products", "orders", "order_items", "payments")
# Trường của API có tên khác cột trong schema core.
CORE_COLUMN_RENAMES = {"orders": {"status": "order_status"}}


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def save_raw(resource: str, rows: list, run_id: str, updated_after: str | None = None) -> Path:
    target = SETTINGS.raw_dir / run_id / f"{resource}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "resource": resource,
        "run_id": run_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "updated_after": updated_after,
        "total": len(rows),
        "data": rows,
    }
    # Mode "x": RAW là bất biến, file của một run đã ghi thì không bao giờ bị ghi đè.
    with target.open("x", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log.info(
        "RAW saved resource=%s rows=%d -> %s",
        resource, len(rows), target.relative_to(SETTINGS.root).as_posix(),
    )
    return target


def extract_api_to_raw(
    run_id: str | None = None,
    resources: tuple = API_RESOURCES,
    updated_after: str | None = None,
    page_size: int = 100,
) -> dict:
    run_id = run_id or new_run_id()
    log.info(
        "API extract start | run_id=%s resources=%s updated_after=%s page_size=%d",
        run_id, ",".join(resources), updated_after, page_size,
    )
    raw_files = {}
    for resource in resources:
        rows = fetch_all_pages(resource, updated_after=updated_after, page_size=page_size)
        raw_files[resource] = save_raw(resource, rows, run_id, updated_after)
    log.info("API extract end | run_id=%s files=%d", run_id, len(raw_files))
    return raw_files


def load_raw_to_core(run_id: str, resources: tuple = API_RESOURCES) -> dict:
    log.info("CORE load start | run_id=%s resources=%s", run_id, ",".join(resources))
    stats = {}
    for resource in resources:
        df = normalize(read_dataset(SETTINGS.raw_dir / run_id / f"{resource}.json"))
        df = df.rename(columns=CORE_COLUMN_RENAMES.get(resource, {}))
        stats[resource] = upsert_dataframe(resource, df)
    log.info(
        "CORE load end | run_id=%s inserted=%d updated=%d",
        run_id,
        sum(s["inserted"] for s in stats.values()),
        sum(s["updated"] for s in stats.values()),
    )
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="API ingestion (API -> RAW)")
    parser.add_argument("--run-id", default=None, help="Mặc định: timestamp UTC hiện tại")
    parser.add_argument(
        "--resources", nargs="+", default=list(API_RESOURCES), choices=API_RESOURCES,
        help="Danh sách resource cần lấy (mặc định: cả 5)",
    )
    parser.add_argument("--updated-after", default=None, help="Mốc ISO 8601 có múi giờ")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--load", action="store_true", help="Upsert RAW vừa lấy vào schema core")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_id = args.run_id or new_run_id()
    resources = tuple(args.resources)
    try:
        extract_api_to_raw(run_id, resources, args.updated_after, args.page_size)
    except (RuntimeError, FileExistsError) as exc:
        log.error("API extract failed | %s: %s", type(exc).__name__, exc)
        sys.exit(1)
    if args.load:
        try:
            load_raw_to_core(run_id, resources)
        except (SQLAlchemyError, ValueError) as exc:
            log.error(
                "CORE load failed, transaction rolled back | %s: %s",
                type(exc).__name__, str(exc).splitlines()[0],
            )
            sys.exit(1)
