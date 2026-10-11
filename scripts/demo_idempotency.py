"""Kiểm thử idempotency: chạy lại pipeline API -> RAW -> core với cùng dữ liệu (Bài 5).

Chạy: python scripts/demo_idempotency.py <run_id_da_nap> > docs/evidence/06-idempotency-log.txt 2>&1
<run_id_da_nap> là run đã được nạp vào core trước đó (Run 1). Script chạy lại pipeline
đầy đủ (Run 2: gọi API, lưu RAW mới, upsert) rồi nạp lại chính RAW đó thêm một lần (Run 3).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import SETTINGS
from src.database import engine
from src.load_postgres import PK
from src.pipeline import API_RESOURCES, extract_api_to_raw, load_raw_to_core, new_run_id

failures = []


def say(text_: str = "") -> None:
    print(text_, flush=True)


def check(label: str, ok: bool) -> None:
    say(f"[{'OK' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def snapshot() -> dict:
    """COUNT(*), COUNT(DISTINCT pk) và md5 toàn bộ nội dung của từng bảng."""
    result = {}
    with engine.connect() as conn:
        for name in API_RESOURCES:
            pk = PK[name]
            rows, distinct, digest = conn.execute(
                text(
                    f"SELECT COUNT(*), COUNT(DISTINCT {pk}), "
                    f"md5(string_agg(t::text, '|' ORDER BY {pk})) FROM core.{name} t"
                )
            ).one()
            result[name] = {"count": rows, "distinct": distinct, "md5": digest}
    return result


def show(label: str, snap: dict) -> None:
    say(label)
    for name, s in snap.items():
        say(f"   core.{name:<12} COUNT(*)={s['count']:<6} COUNT(DISTINCT {PK[name]})={s['distinct']:<6} md5={s['md5'][:12]}...")


def raw_data(run_id: str) -> dict:
    return {
        name: json.loads((SETTINGS.raw_dir / run_id / f"{name}.json").read_text(encoding="utf-8"))["data"]
        for name in API_RESOURCES
    }


def verify_run(label: str, stats: dict, before: dict, after: dict) -> None:
    for name in API_RESOURCES:
        s = stats[name]
        say(f"{label} core.{name}: incoming={s['inserted_or_updated']} inserted={s['inserted']} updated={s['updated']}")
        check(
            f"core.{name}: inserted=0, updated=incoming, COUNT(*) khong doi, COUNT(*)=COUNT(DISTINCT pk)",
            s["inserted"] == 0
            and s["updated"] == s["inserted_or_updated"]
            and after[name]["count"] == before[name]["count"] == after[name]["distinct"],
        )
    check(
        "noi dung 5 bang giong het truoc khi chay (md5 toan bang khong doi)",
        all(after[name]["md5"] == before[name]["md5"] for name in API_RESOURCES),
    )


def main() -> int:
    first_run_id = sys.argv[1]
    say("# 06-idempotency-log — Minh chung kiem thu idempotency (Bai 5)")
    say(f"# Ngay chay: {datetime.now():%Y-%m-%d %H:%M:%S}")
    say(f"# Run 1 (da nap truoc do): data/raw/{first_run_id}/ | Dich: {engine.url.render_as_string(hide_password=True)}")

    say("\n== 1. Trang thai sau Run 1, truoc Run 2")
    before = snapshot()
    show("SELECT COUNT(*), COUNT(DISTINCT pk), md5(noi dung) FROM core.<bang>:", before)

    say("\n== 2. Run 2: chay lai toan bo pipeline (API -> RAW moi -> upsert core)")
    second_run_id = new_run_id()
    say(f"extract_api_to_raw + load_raw_to_core  # tuong duong CLI: python -m src.pipeline --run-id {second_run_id} --load")
    extract_api_to_raw(run_id=second_run_id)
    check(
        "du lieu API cua Run 2 giong het Run 1 (so sanh data cua 5 file RAW)",
        raw_data(first_run_id) == raw_data(second_run_id),
    )
    stats = load_raw_to_core(second_run_id)
    after_second = snapshot()
    show("Sau Run 2:", after_second)
    verify_run("Run 2", stats, before, after_second)

    say("\n== 3. Run 3: nap lai chinh RAW cua Run 2 them mot lan nua")
    say(f"load_raw_to_core('{second_run_id}')")
    stats = load_raw_to_core(second_run_id)
    after_third = snapshot()
    show("Sau Run 3:", after_third)
    verify_run("Run 3", stats, after_second, after_third)

    say("\n== 4. SQL doi soat tren core.orders")
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM core.orders")).scalar_one()
        distinct = conn.execute(text("SELECT COUNT(DISTINCT order_id) FROM core.orders")).scalar_one()
        duplicates = conn.execute(
            text("SELECT COUNT(*) FROM (SELECT order_id FROM core.orders GROUP BY order_id HAVING COUNT(*) > 1) d")
        ).scalar_one()
    say(f"SELECT COUNT(*) FROM core.orders;                 -> {total}")
    say(f"SELECT COUNT(DISTINCT order_id) FROM core.orders; -> {distinct}")
    say(f"So order_id xuat hien nhieu hon 1 lan             -> {duplicates}")
    check("COUNT(*) = COUNT(DISTINCT order_id), khong co khoa trung", total == distinct and duplicates == 0)

    say(f"\nchecks failed: {len(failures)}")
    say(f"\nexit code: {1 if failures else 0}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
