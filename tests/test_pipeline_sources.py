"""Source routing, incremental extraction and RAW preservation contracts."""
import dataclasses
import json

import pandas as pd
import pytest

from src import pipeline


@pytest.fixture
def sources(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "SETTINGS", dataclasses.replace(
        pipeline.SETTINGS, raw_dir=tmp_path / "raw",
    ))
    batch = tmp_path / "batch"
    batch.mkdir()
    for name, filename in pipeline.DATA_FILES.items():
        rows = [{"origin": "file", "dataset": name}]
        path = batch / filename
        if path.suffix == ".json":
            path.write_text(json.dumps(rows), encoding="utf-8")
        else:
            pd.DataFrame(rows).to_csv(path, index=False)
    return batch


@pytest.mark.parametrize("source", ["file", "api", "both"])
def test_routes_sources_and_preserves_raw_before_dataframe(sources, monkeypatch, source):
    api_names = (pipeline.API_RESOURCES if source == "api" else
                 pipeline.TRANSACTION_RESOURCES if source == "both" else ())
    file_names = set(pipeline.API_RESOURCES) - set(api_names)
    # API mode needs no input directory; hybrid needs no transaction files.
    for name in api_names:
        (sources / pipeline.DATA_FILES[name]).unlink()
    state = {"api_watermarks": {name: "2026-07-01T00:00:00Z" for name in api_names}}
    calls = []
    rows = {name: [{"origin": "api", "text": " Hà Nội ", "amount": "001.00",
                    "nullable": None, "nested": {"keep": [1, True]}}] for name in api_names}

    def fetch(name, updated_after=None, page_size=100):
        calls.append((name, updated_after, page_size))
        return rows[name]

    monkeypatch.setattr(pipeline, "fetch_all_pages", fetch)
    reader = pipeline.read_dataset

    def read(path):
        if path.parent.name == "run-1":
            payload = json.loads(path.read_text(encoding="utf-8"))
            assert payload["data"] == rows[path.stem]
            assert payload["updated_after"] == state["api_watermarks"][path.stem]
        return reader(path)

    monkeypatch.setattr(pipeline, "read_dataset", read)
    frames = pipeline._source_frames(sources, source, "run-1", state)
    assert tuple(frames) == pipeline.API_RESOURCES
    assert calls == [(name, state["api_watermarks"][name], 100) for name in api_names]
    for name in file_names:
        assert frames[name].iloc[0]["origin"] == "file"
    for name in api_names:
        assert frames[name].iloc[0]["origin"] == "api"
    snapshots = list(pipeline.SETTINGS.raw_dir.glob("run-1/*.json"))
    assert {path.stem for path in snapshots} == set(api_names)


def test_empty_api_increment_is_captured_with_valid_empty_schema(sources, monkeypatch):
    monkeypatch.setattr(pipeline, "fetch_all_pages", lambda *args, **kwargs: [])
    frames = pipeline._api_frames("empty-run", {})
    for name, frame in frames.items():
        assert frame.empty
        pipeline.schema_validator.validate_schema(name, frame)
        raw = pipeline.SETTINGS.raw_dir / "empty-run" / f"{name}.json"
        assert json.loads(raw.read_text(encoding="utf-8"))["data"] == []


def test_separate_runs_keep_previous_raw_bytes(sources, monkeypatch):
    monkeypatch.setattr(pipeline, "fetch_all_pages", lambda *args, **kwargs: [{"value": " old "}])
    pipeline._api_frames("first", {}, ("orders",))
    original = pipeline.SETTINGS.raw_dir / "first" / "orders.json"
    before = original.read_bytes()
    monkeypatch.setattr(pipeline, "fetch_all_pages", lambda *args, **kwargs: [{"value": "new"}])
    pipeline._api_frames("second", {}, ("orders",))
    assert original.read_bytes() == before
    with pytest.raises(FileExistsError):
        pipeline._api_frames("first", {}, ("orders",))
    assert original.read_bytes() == before
