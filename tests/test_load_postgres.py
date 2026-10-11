import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from src.database import engine
from src.load_postgres import PK, build_upsert_sql, to_records, upsert_dataframe, upsert_on_connection


def customer(customer_id, **overrides):
    row = {
        "customer_id": customer_id,
        "full_name": "Test User",
        "email": f"{customer_id}@pytest.example.com".lower(),
        "phone": "0900000000",
        "city": "Ha Noi",
        "customer_segment": "Gold",
        "status": "active",
        "source_system": "pytest",
        "created_at": pd.Timestamp("2026-07-01T08:00:00+07:00"),
        "updated_at": pd.Timestamp("2026-07-01T09:00:00+07:00"),
    }
    return {**row, **overrides}


@pytest.fixture
def conn():
    """Kết nối PostgreSQL thật; mọi thay đổi được rollback sau mỗi test."""
    try:
        connection = engine.connect()
    except OperationalError:
        pytest.skip("PostgreSQL chưa chạy")
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


def count(conn, where="TRUE"):
    return conn.execute(text(f"SELECT COUNT(*) FROM core.customers WHERE {where}")).scalar_one()


def test_pk_mapping_matches_core_tables():
    assert PK == {
        "customers": "customer_id",
        "products": "product_id",
        "orders": "order_id",
        "order_items": "order_item_id",
        "payments": "payment_id",
    }


def test_build_upsert_sql_excludes_pk_from_update():
    sql = build_upsert_sql("orders", ["order_id", "customer_id", "order_total"])

    assert sql == (
        "INSERT INTO core.orders (order_id, customer_id, order_total) "
        "VALUES (:order_id, :customer_id, :order_total) "
        "ON CONFLICT (order_id) DO UPDATE SET "
        "customer_id = EXCLUDED.customer_id, order_total = EXCLUDED.order_total"
    )


def test_to_records_converts_missing_values_to_none_and_numpy_to_python():
    df = pd.DataFrame(
        {
            "a": [1.5, np.nan],
            "b": pd.to_datetime(["2026-07-01T08:00:00Z", None], utc=True),
            "c": pd.array([1, pd.NA], dtype="Int64"),
            "d": ["x", None],
            "e": np.array([7, 8], dtype="int64"),
        }
    )

    first, second = to_records(df)

    assert second == {"a": None, "b": None, "c": None, "d": None, "e": 8}
    assert type(first["e"]) is int and type(first["a"]) is float


def test_upsert_inserts_then_updates_without_duplicates(conn):
    before = count(conn)
    df = pd.DataFrame([customer("PYT000001"), customer("PYT000002")])

    first = upsert_on_connection(conn, "customers", df)
    df.loc[0, "city"] = "Da Nang"
    second = upsert_on_connection(conn, "customers", df)

    assert first == {"inserted": 2, "updated": 0, "inserted_or_updated": 2}
    assert second == {"inserted": 0, "updated": 2, "inserted_or_updated": 2}
    assert count(conn) == before + 2
    assert count(conn, "customer_id = 'PYT000001' AND city = 'Da Nang'") == 1


def test_upsert_counts_mixed_insert_and_update(conn):
    upsert_on_connection(conn, "customers", pd.DataFrame([customer("PYT000001")]))

    stats = upsert_on_connection(
        conn,
        "customers",
        pd.DataFrame([customer("PYT000001"), customer("PYT000002"), customer("PYT000003")]),
    )

    assert stats == {"inserted": 2, "updated": 1, "inserted_or_updated": 3}


def test_upsert_writes_nan_and_na_as_null(conn):
    df = pd.DataFrame([customer("PYT000001", phone=np.nan, city=pd.NA)])

    upsert_on_connection(conn, "customers", df)

    assert count(conn, "customer_id = 'PYT000001' AND phone IS NULL AND city IS NULL") == 1


def test_upsert_ignores_error_code_column(conn):
    df = pd.DataFrame([customer("PYT000001", error_code=None)])

    stats = upsert_on_connection(conn, "customers", df)

    assert stats["inserted"] == 1


def test_upsert_empty_dataframe_is_noop(conn):
    df = pd.DataFrame([customer("PYT000001")]).iloc[0:0]

    stats = upsert_on_connection(conn, "customers", df)

    assert stats == {"inserted": 0, "updated": 0, "inserted_or_updated": 0}


def test_upsert_rejects_unknown_table(conn):
    df = pd.DataFrame([customer("PYT000001")])

    with pytest.raises(ValueError, match="Unknown core table"):
        upsert_on_connection(conn, "customers; DROP TABLE core.orders", df)


def test_upsert_rejects_columns_not_in_table(conn):
    df = pd.DataFrame([customer("PYT000001", not_a_column=1)])

    with pytest.raises(ValueError, match="not_a_column"):
        upsert_on_connection(conn, "customers", df)


def test_upsert_rejects_null_primary_key(conn):
    df = pd.DataFrame([customer("PYT000001"), customer(None, email="x@pytest.example.com")])

    with pytest.raises(ValueError, match="NULL primary key"):
        upsert_on_connection(conn, "customers", df)


def test_upsert_dataframe_rolls_back_whole_batch_on_constraint_violation(conn):
    df = pd.DataFrame(
        [customer("PYT000001"), customer("PYT000002"), customer("PYT000003", status="banned")]
    )

    with pytest.raises(IntegrityError):
        upsert_dataframe("customers", df)

    assert count(conn, "customer_id LIKE 'PYT%'") == 0
