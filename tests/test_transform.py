import pandas as pd

from src.transform import normalize


def test_normalize_raw_immutability():
    raw = pd.DataFrame(
        {
            " Order_ID ": [" ORD1 ", "ORD2"],
            "STATUS": ["Completed", " PENDING "],
            "order_total": ["100.5", "abc"],
            "order_date": ["2026-07-01T18:57:00+07:00", "bad-date"],
        }
    )
    snapshot = raw.copy(deep=True)

    out = normalize(raw)

    assert out is not raw
    pd.testing.assert_frame_equal(raw, snapshot)
    assert list(raw.columns) == [" Order_ID ", "STATUS", "order_total", "order_date"]


def test_normalize_column_names():
    raw = pd.DataFrame({" Order_ID ": ["ORD1"], "Channel ": ["web"], "EMAIL": ["a@b.com"]})

    out = normalize(raw)

    assert list(out.columns) == ["order_id", "channel", "email"]


def test_normalize_strings_and_enums():
    raw = pd.DataFrame(
        {
            "full_name": ["  Glenda Crosby ", "Keith Liu  "],
            "Email": [" User01@Example.COM ", None],
            "STATUS": [" Active", "INACTIVE "],
            "payment_method": ["E_Wallet ", " BANK_TRANSFER"],
            "payment_status": ["SUCCESS", " Refunded "],
            "Channel ": [" Mobile_App", "WEB"],
        }
    )

    out = normalize(raw)

    assert out["full_name"].tolist() == ["Glenda Crosby", "Keith Liu"]
    assert out["email"][0] == "user01@example.com"
    assert pd.isna(out["email"][1])
    assert out["status"].tolist() == ["active", "inactive"]
    assert out["payment_method"].tolist() == ["e_wallet", "bank_transfer"]
    assert out["payment_status"].tolist() == ["success", "refunded"]
    assert out["channel"].tolist() == ["mobile_app", "web"]


def test_normalize_keeps_non_string_values_in_object_columns():
    raw = pd.DataFrame({"status": [" Active ", 1, None], "note": [" x ", 2.5, None]})

    out = normalize(raw)

    assert out["status"].tolist()[:2] == ["active", 1]
    assert out["note"].tolist()[:2] == ["x", 2.5]
    assert pd.isna(out["status"][2]) and pd.isna(out["note"][2])


def test_normalize_numeric_and_datetime():
    raw = pd.DataFrame(
        {
            "quantity": ["2", " 1", "abc"],
            "unit_price": ["6980000.00", "150000.5", "N/A"],
            "amount": ["100", "-500", None],
            "order_date": ["2026-07-01T18:57:00+07:00", "2026-07-02T00:30:00+07:00", "bad-date"],
            "created_at": ["2026-07-01T00:00:00Z", "2026-07-01T07:00:00+07:00", None],
        }
    )

    out = normalize(raw)

    for col in ("quantity", "unit_price", "amount"):
        assert pd.api.types.is_numeric_dtype(out[col])
    assert out["quantity"].tolist()[:2] == [2, 1]
    assert pd.isna(out["quantity"][2])
    assert out["unit_price"].tolist()[:2] == [6980000.0, 150000.5]
    assert pd.isna(out["unit_price"][2])
    assert out["amount"].tolist()[:2] == [100, -500]

    for col in ("order_date", "created_at"):
        assert str(out[col].dtype) == "datetime64[ns, UTC]"
    assert out["order_date"][0] == pd.Timestamp("2026-07-01 11:57:00", tz="UTC")
    assert out["order_date"][1] == pd.Timestamp("2026-07-01 17:30:00", tz="UTC")
    assert pd.isna(out["order_date"][2])
    assert out["created_at"][0] == out["created_at"][1] == pd.Timestamp("2026-07-01", tz="UTC")
    assert pd.isna(out["created_at"][2])
