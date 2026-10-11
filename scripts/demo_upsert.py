"""Demo upsert RAW -> core của src/load_postgres.py (Bài 4).

Chạy: python scripts/demo_upsert.py [run_id] [--checks-only] > docs/evidence/06-upsert-log.txt 2>&1
Mục 1-3 nạp thật (commit) dữ liệu của run vào schema core và thử một lô lỗi.
Mục 4-5 chỉ kiểm chứng hành vi, mọi thay đổi đều được rollback.
--checks-only: bỏ qua mục 1-3, chỉ chạy mục 4-5 (không ghi gì vào database).
"""
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import SETTINGS
from src.database import engine
from src.load_postgres import PK, build_upsert_sql, upsert_dataframe, upsert_on_connection
from src.pipeline import API_RESOURCES, CORE_COLUMN_RENAMES, load_raw_to_core
from src.transform import normalize

failures = []


def say(text_: str = "") -> None:
    print(text_, flush=True)


def check(label: str, ok: bool) -> None:
    say(f"[{'OK' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def counts() -> dict:
    with engine.connect() as conn:
        return {
            name: conn.execute(text(f"SELECT COUNT(*) FROM core.{name}")).scalar_one()
            for name in API_RESOURCES
        }


def latest_run_id() -> str:
    runs = sorted(p.name for p in SETTINGS.raw_dir.iterdir() if p.is_dir())
    return runs[-1]


def raw_rows(run_id: str, name: str) -> list:
    path = SETTINGS.raw_dir / run_id / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))["data"]


def demo_customer(customer_id: str, **overrides) -> dict:
    row = {
        "customer_id": customer_id,
        "full_name": "Demo Rollback",
        "email": f"{customer_id}@demo.example.com".lower(),
        "phone": "0900000000",
        "city": "Ha Noi",
        "customer_segment": "Gold",
        "status": "active",
        "source_system": "demo_upsert",
        "created_at": pd.Timestamp("2026-07-01T08:00:00+07:00"),
        "updated_at": pd.Timestamp("2026-07-01T09:00:00+07:00"),
    }
    return {**row, **overrides}


def load_and_verify(run_id: str) -> None:
    say("\n== 1. Cau lenh UPSERT duoc sinh tu dong (vi du core.orders)")
    say(build_upsert_sql("orders", [
        "order_id", "customer_id", "order_date", "order_status", "shipping_city",
        "channel", "order_total", "source_system", "created_at", "updated_at",
    ]))

    say("\n== 2. Nap 5 bang RAW -> core (moi bang 1 transaction, engine.begin())")
    before = counts()
    say(f"COUNT(*) truoc khi nap: {before}")
    stats = load_raw_to_core(run_id)
    after = counts()
    say(f"COUNT(*) sau khi nap:   {after}")
    for name in API_RESOURCES:
        s = stats[name]
        say(f"[UPSERT] table=core.{name} incoming={s['inserted_or_updated']} inserted={s['inserted']} "
            f"updated={s['updated']} | Verification: SELECT COUNT(*) FROM core.{name} = {after[name]} "
            f"(truoc: {before[name]})")
        check(
            f"core.{name}: inserted + updated = incoming, COUNT(*) tang dung bang inserted",
            s["inserted"] + s["updated"] == s["inserted_or_updated"]
            and after[name] == before[name] + s["inserted"],
        )
    with engine.connect() as conn:
        for name in API_RESOURCES:
            ids = [row[PK[name]] for row in raw_rows(run_id, name)]
            found, distinct = conn.execute(
                text(f"SELECT COUNT(*), COUNT(DISTINCT {PK[name]}) FROM core.{name} WHERE {PK[name]} = ANY(:ids)"),
                {"ids": ids},
            ).one()
            check(f"core.{name}: {found}/{len(ids)} khoa cua RAW co trong DB, khong trung", found == distinct == len(ids))
        raw_order = raw_rows(run_id, "orders")[0]
        db_order = conn.execute(
            text("SELECT order_id, order_status, order_total, updated_at FROM core.orders WHERE order_id = :id"),
            {"id": raw_order["order_id"]},
        ).one()
        say(f"RAW : order_id={raw_order['order_id']} status={raw_order['status']} "
            f"order_total={raw_order['order_total']!r} updated_at={raw_order['updated_at']}")
        say(f"CORE: order_id={db_order.order_id} order_status={db_order.order_status} "
            f"order_total={db_order.order_total!r} updated_at={db_order.updated_at.isoformat()}")
        check(
            "gia tri trong core khop RAW (NUMERIC, timestamptz cung thoi diem)",
            db_order.order_total == Decimal(raw_order["order_total"])
            and db_order.updated_at == datetime.fromisoformat(raw_order["updated_at"])
            and db_order.order_status == raw_order["status"],
        )

    say("\n== 3. Transaction rollback khi vi pham rang buoc")
    batch = pd.DataFrame([
        demo_customer("DEMO00001"),
        demo_customer("DEMO00002"),
        demo_customer("DEMO00003", status="banned"),
    ])
    say("upsert_dataframe('customers', 3 dong: 2 dong hop le + 1 dong status='banned')")
    try:
        upsert_dataframe("customers", batch)
        say("-> nap thanh cong (SAI)")
        raised = False
    except IntegrityError as exc:
        say(f"-> IntegrityError: {str(exc.orig).splitlines()[0]}")
        raised = True
    with engine.connect() as conn:
        leftover = conn.execute(
            text("SELECT COUNT(*) FROM core.customers WHERE customer_id LIKE 'DEMO%'")
        ).scalar_one()
    say(f"SELECT COUNT(*) FROM core.customers WHERE customer_id LIKE 'DEMO%' = {leftover}")
    check("ca lo bi rollback: 2 dong hop le cung khong duoc ghi", raised and leftover == 0)
    check("COUNT(*) cac bang khong doi sau lo loi", counts() == after)


def verify_behaviour(run_id: str) -> None:
    before = counts()
    raw_order = raw_rows(run_id, "orders")[0]

    say("\n== 4. Update ban ghi da ton tai (chay trong transaction, sau do rollback)")
    with engine.connect() as conn:
        transaction = conn.begin()
        changed = normalize(pd.DataFrame([raw_order])).rename(columns=CORE_COLUMN_RENAMES["orders"])
        changed.loc[0, ["order_total", "shipping_city"]] = [1.0, "Demo City"]
        say(f"upsert lai {raw_order['order_id']} voi order_total=1.0, shipping_city='Demo City'")
        result = upsert_on_connection(conn, "orders", changed)
        row = conn.execute(
            text("SELECT order_total, shipping_city, customer_id FROM core.orders WHERE order_id = :id"),
            {"id": raw_order["order_id"]},
        ).one()
        total_rows = conn.execute(text("SELECT COUNT(*) FROM core.orders")).scalar_one()
        say(f"-> {result} | order_total={row.order_total} shipping_city={row.shipping_city} "
            f"customer_id={row.customer_id} | COUNT(*)={total_rows}")
        check(
            "khoa da ton tai -> updated=1, inserted=0, gia tri moi ghi de, khong them dong",
            result == {"inserted": 0, "updated": 1, "inserted_or_updated": 1}
            and row.order_total == 1 and row.shipping_city == "Demo City"
            and row.customer_id == raw_order["customer_id"]
            and total_rows == before["orders"],
        )
        transaction.rollback()
    with engine.connect() as conn:
        restored = conn.execute(
            text("SELECT order_total FROM core.orders WHERE order_id = :id"), {"id": raw_order["order_id"]}
        ).scalar_one()
    say(f"sau rollback: order_total={restored}")
    check("rollback tra lai gia tri cu", restored == Decimal(raw_order["order_total"]))

    say("\n== 5. NaN / NaT / <NA> cua pandas -> NULL (chay trong transaction, sau do rollback)")
    with engine.connect() as conn:
        transaction = conn.begin()
        dirty = pd.DataFrame([demo_customer("DEMO00009", phone=np.nan, city=pd.NA)])
        say(f"dau vao: phone={dirty.loc[0, 'phone']!r} city={dirty.loc[0, 'city']!r}")
        upsert_on_connection(conn, "customers", dirty)
        row = conn.execute(
            text("SELECT phone IS NULL AS phone_null, city IS NULL AS city_null FROM core.customers "
                 "WHERE customer_id = 'DEMO00009'")
        ).one()
        say(f"trong DB: phone IS NULL = {row.phone_null} | city IS NULL = {row.city_null}")
        check("NaN va <NA> duoc ghi thanh NULL", row.phone_null and row.city_null)
        transaction.rollback()
    check("COUNT(*) cac bang khong doi sau muc 4-5 (da rollback het)", counts() == before)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    checks_only = "--checks-only" in sys.argv
    run_id = args[0] if args else latest_run_id()

    if checks_only:
        say(f"# Muc 4-5 chay rieng luc {datetime.now():%Y-%m-%d %H:%M:%S}: "
            f"python scripts/demo_upsert.py {run_id} --checks-only")
    else:
        say("# 06-upsert-log — Minh chung UPSERT vao PostgreSQL schema core (Bai 4)")
        say(f"# Ngay chay: {datetime.now():%Y-%m-%d %H:%M:%S}")
        say(f"# Nguon: data/raw/{run_id}/ | Dich: {engine.url.render_as_string(hide_password=True)}")
        load_and_verify(run_id)
    verify_behaviour(run_id)

    say(f"\nchecks failed: {len(failures)}")
    say(f"\nexit code: {1 if failures else 0}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
