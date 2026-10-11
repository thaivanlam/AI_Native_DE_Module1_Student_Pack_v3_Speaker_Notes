import dataclasses
import json

import pytest

from src import pipeline
from src.config import SETTINGS
from src.extract_files import read_dataset


@pytest.fixture
def raw_dir(tmp_path, monkeypatch):
    settings = dataclasses.replace(SETTINGS, root=tmp_path, raw_dir=tmp_path / "data" / "raw")
    monkeypatch.setattr(pipeline, "SETTINGS", settings)
    return settings.raw_dir


def test_save_raw_writes_rows_unchanged(raw_dir):
    rows = [
        {"order_id": "ORD1", "order_total": "19156500.00", "shipping_city": " Hà Nội "},
        {"order_id": "ORD2", "order_total": "0.00", "shipping_city": None},
    ]

    path = pipeline.save_raw("orders", rows, "run-1", updated_after="2026-07-01T12:00:00Z")

    assert path == raw_dir / "run-1" / "orders.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["data"] == rows
    assert payload["total"] == 2
    assert payload["resource"] == "orders"
    assert payload["run_id"] == "run-1"
    assert payload["updated_after"] == "2026-07-01T12:00:00Z"


def test_save_raw_never_overwrites_existing_file(raw_dir):
    path = pipeline.save_raw("orders", [{"order_id": "ORD1"}], "run-1")
    before = path.read_bytes()

    with pytest.raises(FileExistsError):
        pipeline.save_raw("orders", [{"order_id": "CHANGED"}], "run-1")

    assert path.read_bytes() == before


def test_raw_file_readable_by_read_dataset(raw_dir):
    path = pipeline.save_raw("orders", [{"order_id": "ORD1"}, {"order_id": "ORD2"}], "run-1")

    df = read_dataset(path)

    assert df["order_id"].tolist() == ["ORD1", "ORD2"]


def test_extract_api_to_raw_saves_each_resource_in_dependency_order(raw_dir, monkeypatch):
    fetched = []

    def fake_fetch(resource, updated_after=None, page_size=100):
        fetched.append((resource, updated_after, page_size))
        return [{"id": f"{resource}-1"}]

    monkeypatch.setattr(pipeline, "fetch_all_pages", fake_fetch)

    files = pipeline.extract_api_to_raw(run_id="run-1", updated_after="2026-07-01T12:00:00Z")

    assert [f[0] for f in fetched] == ["customers", "products", "orders", "order_items", "payments"]
    assert all(f[1] == "2026-07-01T12:00:00Z" for f in fetched)
    assert sorted(p.name for p in (raw_dir / "run-1").iterdir()) == [
        "customers.json", "order_items.json", "orders.json", "payments.json", "products.json",
    ]
    assert json.loads(files["order_items"].read_text(encoding="utf-8"))["data"] == [
        {"id": "order_items-1"}
    ]


def test_extract_api_to_raw_stops_before_saving_when_fetch_fails(raw_dir, monkeypatch):
    def fake_fetch(resource, updated_after=None, page_size=100):
        if resource == "products":
            raise RuntimeError("API failed after 3 attempts: products page 1")
        return [{"id": 1}]

    monkeypatch.setattr(pipeline, "fetch_all_pages", fake_fetch)

    with pytest.raises(RuntimeError):
        pipeline.extract_api_to_raw(run_id="run-1")

    assert [p.name for p in (raw_dir / "run-1").iterdir()] == ["customers.json"]
