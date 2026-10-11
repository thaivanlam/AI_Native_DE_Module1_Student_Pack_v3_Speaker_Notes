import pandas as pd
from sqlalchemy import text

from src.database import engine
from src.logger import get_logger

log = get_logger("load")

PK = {
    "customers": "customer_id",
    "products": "product_id",
    "orders": "order_id",
    "order_items": "order_item_id",
    "payments": "payment_id",
}
TECHNICAL_COLUMNS = ("error_code",)


def build_upsert_sql(name: str, columns: list) -> str:
    pk = PK[name]
    cols = ", ".join(columns)
    placeholders = ", ".join(f":{col}" for col in columns)
    updates = ", ".join(f"{col} = EXCLUDED.{col}" for col in columns if col != pk)
    action = f"DO UPDATE SET {updates}" if updates else "DO NOTHING"
    return (
        f"INSERT INTO core.{name} ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT ({pk}) {action}"
    )


def to_records(df: pd.DataFrame) -> list:
    """NaN/NaT/<NA> -> None (NULL), giá trị numpy -> kiểu Python thuần để bind vào SQL."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


def _table_columns(conn, name: str) -> set:
    rows = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'core' AND table_name = :name"
        ),
        {"name": name},
    )
    return {row[0] for row in rows}


def upsert_on_connection(conn, name: str, df: pd.DataFrame) -> dict:
    """Upsert trong transaction của `conn`; bên gọi quyết định commit hay rollback."""
    if name not in PK:
        raise ValueError(f"Unknown core table: {name}")
    pk = PK[name]

    df = df.drop(columns=list(TECHNICAL_COLUMNS), errors="ignore")
    if pk not in df.columns:
        raise ValueError(f"Missing primary key column {pk} for core.{name}")
    # Tên bảng/cột được ghép vào câu SQL nên phải khớp với schema thật, không nhận tên lạ.
    unknown = sorted(set(df.columns) - _table_columns(conn, name))
    if unknown:
        raise ValueError(f"Columns not in core.{name}: {unknown}")

    records = to_records(df)
    if not records:
        log.info("[UPSERT] table=core.%s incoming=0 inserted=0 updated=0", name)
        return {"inserted": 0, "updated": 0, "inserted_or_updated": 0}
    if any(record[pk] is None for record in records):
        raise ValueError(f"NULL primary key {pk} in data for core.{name}")

    incoming_ids = {record[pk] for record in records}
    existing_ids = {
        row[0]
        for row in conn.execute(
            text(f"SELECT {pk} FROM core.{name} WHERE {pk} = ANY(:ids)"),
            {"ids": list(incoming_ids)},
        )
    }

    conn.execute(text(build_upsert_sql(name, list(df.columns))), records)

    inserted = len(incoming_ids - existing_ids)
    updated = len(incoming_ids & existing_ids)
    log.info(
        "[UPSERT] table=core.%s incoming=%d inserted=%d updated=%d",
        name, len(records), inserted, updated,
    )
    return {"inserted": inserted, "updated": updated, "inserted_or_updated": len(records)}


def upsert_dataframe(name: str, df: pd.DataFrame) -> dict:
    # engine.begin(): commit khi cả lô thành công, rollback toàn bộ nếu có dòng lỗi.
    with engine.begin() as conn:
        return upsert_on_connection(conn, name, df)
