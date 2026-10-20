"""B8/Bai 4: real PostgreSQL evidence in a disposable, isolated database.

Run: .venv/Scripts/python.exe -m scripts.demo_mart_reconciliation
Requires CREATEDB permission. Reads the configured Core, never changes it.
"""
import csv
import dataclasses
import logging
import tempfile
import uuid
from pathlib import Path

import pandas as pd
from psycopg import sql
from sqlalchemy import create_engine

from src import pipeline, refresh_mart
from src.database import engine as source_engine
from src import load_postgres


def main():
    root = pipeline.SETTINGS.root
    name = "b8_mart_demo_" + uuid.uuid4().hex[:12]
    target_engine = create_engine(source_engine.url.set(database=name))
    evidence = root / "docs/evidence/08-mart-refresh.txt"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(evidence, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    demo_log = logging.getLogger("mart_demo")
    demo_log.setLevel(logging.INFO)
    loggers = [demo_log, pipeline.log, refresh_mart.log, logging.getLogger("load")]
    for logger in loggers:
        logger.addHandler(handler)
    created = False
    original_settings = pipeline.SETTINGS, refresh_mart.SETTINGS
    original_engines = refresh_mart.engine, load_postgres.engine
    try:
        with source_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.exec_driver_sql(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)).as_string())
        created = True
        demo_log.info("Real PostgreSQL demo database=%s; configured source database is read-only", name)
        batch = root / "data/incremental/day_2026-07-01"
        daily_ids = set(pd.read_csv(batch / "orders_daily.csv")["order_id"])
        raw = target_engine.raw_connection()
        try:
            with raw.cursor() as cursor:
                cursor.execute((root / "sql/student/01_create_oltp.sql").read_text(encoding="utf-8"))
                for table in ("categories", "customers", "products", "order_status", "orders", "order_items", "payments"):
                    with source_engine.connect() as source:
                        result = source.exec_driver_sql(f"SELECT * FROM core.{table}")
                        columns = list(result.keys())
                        rows = result.fetchall()
                    if table in {"orders", "order_items", "payments"}:
                        index = columns.index("order_id")
                        rows = [tuple(row) for row in rows if row[index] not in daily_ids]
                    else:
                        rows = [tuple(row) for row in rows]
                    # The DDL seeds order_status; copy the configured lookup exactly.
                    cursor.execute(sql.SQL("DELETE FROM core.{}").format(sql.Identifier(table)))
                    statement = sql.SQL("INSERT INTO core.{} ({}) VALUES ({})").format(
                        sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, columns)),
                        sql.SQL(",").join(sql.Placeholder() for _ in columns))
                    cursor.executemany(statement, rows)
                    demo_log.info("Baseline core.%s rows=%d (daily orders excluded)", table, len(rows))
                # Exercise migration from the existing Buoi 4 schema, too.
                cursor.execute((root / "sql/student/04_data_mart.sql").read_text(encoding="utf-8"))
                demo_log.info("Loaded legacy Buoi 4 mart (revenue column, no net_amount)")
            raw.commit()
        finally:
            raw.close()

        # Use real validators/files and direct all database writes to the demo.
        refresh_mart.engine = target_engine
        load_postgres.engine = target_engine
        with tempfile.TemporaryDirectory(prefix="b8_mart_") as temporary:
            scratch = Path(temporary)
            pipeline.SETTINGS = dataclasses.replace(pipeline.SETTINGS,
                metadata_dir=scratch / "metadata", report_dir=scratch / "reports")
            refresh_mart.SETTINGS = dataclasses.replace(refresh_mart.SETTINGS, root=scratch)
            sql_dir = scratch / "sql/solutions"
            sql_dir.mkdir(parents=True)
            (sql_dir / "12_load_data_mart.sql").write_text(
                (root / "sql/solutions/12_load_data_mart.sql").read_text(encoding="utf-8"), encoding="utf-8")
            demo_log.info("INITIAL BASELINE REFRESH")
            refresh_mart.refresh_mart()
            demo_log.info("INCREMENTAL CLI: --source file --input-dir %s --refresh-mart", batch)
            exit_code = pipeline.main(["--source", "file", "--input-dir", str(batch), "--refresh-mart"])
            if exit_code:
                raise RuntimeError(f"Incremental pipeline exit code={exit_code}")
            comparison = (scratch / "docs/kpi_comparison.csv").read_bytes()

            with target_engine.connect() as connection:
                expected = connection.exec_driver_sql("""
                    SELECT COALESCE(SUM(i.quantity*i.unit_price-i.discount_amount), 0),
                           COUNT(DISTINCT o.order_id),
                           COUNT(DISTINCT o.order_id) FILTER (WHERE o.order_status='completed'),
                           COALESCE(SUM(i.quantity), 0)
                    FROM core.order_items i JOIN core.orders o USING (order_id)
                    WHERE o.order_id = ANY(%s)
                """, (list(daily_ids),)).one()
                calendar = connection.exec_driver_sql(
                    "SELECT MIN(full_date), MAX(full_date), COUNT(*) FROM mart.dim_date").one()
                duplicates = connection.exec_driver_sql(
                    "SELECT COUNT(*)-COUNT(DISTINCT order_item_id) FROM mart.fact_sales").scalar_one()
                amount_diff = connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM mart.fact_sales WHERE net_amount <> revenue").scalar_one()
            from decimal import Decimal
            for row, value in zip(csv.DictReader(comparison.decode().splitlines()), expected, strict=True):
                assert Decimal(row["diff"]) == value, (row, value)
                demo_log.info("Core batch reconciliation %s expected_diff=%s actual_diff=%s OK",
                              row["kpi"], value, row["diff"])
            assert str(calendar[0]) == "2025-01-01" and str(calendar[1]) == "2027-12-31" and calendar[2] == 1095
            assert duplicates == 0 and amount_diff == 0
            demo_log.info("Calendar=%s; duplicate facts=%s; net_amount/revenue mismatches=%s", calendar, duplicates, amount_diff)
            demo_log.info("REPLAY SAME BATCH: assert zero KPI changes")
            assert pipeline.main(["--source", "file", "--input-dir", str(batch), "--refresh-mart"]) == 0
            replay = list(csv.DictReader((scratch / "docs/kpi_comparison.csv").read_text().splitlines()))
            assert all(Decimal(row["diff"]) == 0 for row in replay)
            demo_log.info("Idempotency OK: all four replay diffs are zero")
            (root / "docs/kpi_comparison.csv").write_bytes(comparison)
            demo_log.info("Saved incremental comparison (before replay) to docs/kpi_comparison.csv; exit 0")
    finally:
        pipeline.SETTINGS, refresh_mart.SETTINGS = original_settings
        refresh_mart.engine, load_postgres.engine = original_engines
        target_engine.dispose()
        if created:
            with source_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
                admin.exec_driver_sql(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)).as_string())
            demo_log.info("Dropped disposable database %s; configured Core/Mart/checkpoint unchanged", name)
        for logger in loggers:
            logger.removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    main()
