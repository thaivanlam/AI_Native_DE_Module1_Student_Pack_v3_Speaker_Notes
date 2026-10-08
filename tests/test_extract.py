import json

import pandas as pd
import pytest

from src.extract_files import profile, read_dataset


def test_read_csv_success(tmp_path):
    path = tmp_path / "customers.csv"
    path.write_text("customer_id,email\nCUS1,a@b.com\nCUS2,c@d.com\n", encoding="utf-8")

    df = read_dataset(path)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["customer_id", "email"]
    assert len(df) == 2
    assert df.loc[0, "customer_id"] == "CUS1"


def test_read_csv_with_bom(tmp_path):
    path = tmp_path / "bom.csv"
    path.write_bytes(b"\xef\xbb\xbfid,name\n1,a\n")

    df = read_dataset(path)

    assert list(df.columns) == ["id", "name"]


@pytest.mark.parametrize("wrap", [False, True], ids=["list", "data_wrapper"])
def test_read_json_nested_data(tmp_path, wrap):
    records = [
        {"payment_id": "PAY1", "amount": "100.00"},
        {"payment_id": "PAY2", "amount": "250.50"},
    ]
    path = tmp_path / "payments.json"
    path.write_text(json.dumps({"data": records} if wrap else records), encoding="utf-8")

    df = read_dataset(path)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["payment_id", "amount"]
    assert df["payment_id"].tolist() == ["PAY1", "PAY2"]


def test_read_file_not_found(tmp_path):
    missing = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError, match="Missing file"):
        read_dataset(missing)


def test_unsupported_file_extension(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file"):
        read_dataset(path)


@pytest.mark.parametrize(
    "name, content",
    [("header_only.csv", "id,name\n"), ("zero_bytes.csv", ""), ("empty_list.json", "[]")],
)
def test_empty_dataset_rejected(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="Empty dataset"):
        read_dataset(path)


def test_profile_metrics():
    df = pd.DataFrame(
        {
            "id": [1, 2, 2, 4, None],
            "mixed": ["a", 1, 1, 2.5, None],
            "amount": [10.0, None, None, 3.0, 5.0],
        }
    )

    result = profile(df)

    assert result == {
        "rows": 5,
        "columns": ["id", "mixed", "amount"],
        "missing": {"id": 1, "mixed": 1, "amount": 2},
        "duplicates": 1,
    }
    assert type(result["rows"]) is int
    assert type(result["duplicates"]) is int
