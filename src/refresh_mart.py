"""Incrementally refresh Sales Data Mart and reconcile four business KPIs."""
import csv
import os
import tempfile
from decimal import Decimal
from pathlib import Path

from src.config import SETTINGS
from src.database import engine
from src.logger import get_logger

log = get_logger("refresh_mart")
KPI_NAMES = ("total_revenue", "order_count", "completed_orders", "total_items_sold")
KPI_SQL = """
SELECT COALESCE(SUM(f.net_amount), 0) AS total_revenue,
       COUNT(DISTINCT f.order_id) AS order_count,
       COUNT(DISTINCT f.order_id) FILTER (WHERE s.order_status = 'completed')
         AS completed_orders,
       COALESCE(SUM(f.quantity), 0) AS total_items_sold
FROM mart.fact_sales f
JOIN mart.dim_order_status s ON s.order_status_key = f.order_status_key
"""


def _read_kpis(cursor) -> dict:
    # revenue equals generated net_amount and also works on the Buoi 4 schema
    # before its first migration (which has revenue but no net_amount yet).
    cursor.execute("SELECT to_regclass('mart.fact_sales')")
    if cursor.fetchone()[0] is None:
        return dict.fromkeys(KPI_NAMES, 0)
    cursor.execute("""SELECT EXISTS (SELECT 1 FROM information_schema.columns
                      WHERE table_schema = 'mart' AND table_name = 'fact_sales'
                        AND column_name = 'net_amount')""")
    query = KPI_SQL if cursor.fetchone()[0] else KPI_SQL.replace("f.net_amount", "f.revenue")
    cursor.execute(query)
    return dict(zip(KPI_NAMES, cursor.fetchone(), strict=True))


def write_comparison(before: dict, after: dict, path: Path) -> list[dict]:
    """Keep decimal precision and atomically replace the last successful CSV."""
    rows = [{"kpi": name, "before": before[name], "after": after[name],
             "diff": after[name] - before[name]} for name in KPI_NAMES]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=("kpi", "before", "after", "diff"))
            writer.writeheader()
            for row in rows:
                writer.writerow({key: format(Decimal(value), ".2f")
                                 if row["kpi"] == "total_revenue" and key != "kpi" else value
                                 for key, value in row.items()})
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return rows


def refresh_mart() -> list[dict]:
    """Snapshot mart KPIs, load Core deltas, commit, then publish Before/After.

    Before is the last published mart, even though Core was loaded by step 5.
    Existing facts retain measures/status per ON CONFLICT DO NOTHING; source
    corrections require a separate rebuild policy.
    """
    sql_path = SETTINGS.root / "sql" / "solutions" / "12_load_data_mart.sql"
    sql = sql_path.read_text(encoding="utf-8")
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(804012)")
            before = _read_kpis(cursor)
            log.info("KPI before=%s", before)
            log.info("Executing mart refresh SQL: %s", sql_path)
            cursor.execute(sql)
            after = _read_kpis(cursor)
        connection.commit()
        log.info("Mart refresh committed | KPI after=%s", after)
    except Exception:
        connection.rollback()
        log.exception("Mart refresh failed; rolled back")
        raise
    finally:
        connection.close()
    path = SETTINGS.root / "docs" / "kpi_comparison.csv"
    rows = write_comparison(before, after, path)
    for row in rows:
        log.info("KPI %(kpi)s before=%(before)s after=%(after)s diff=%(diff)s", row)
    log.info("KPI comparison saved: %s", path)
    return rows


if __name__ == "__main__":
    refresh_mart()
