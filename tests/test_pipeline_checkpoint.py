"""Checkpoint durability and timestamp edge cases without external services."""
import dataclasses

import pandas as pd
import pytest

from src import pipeline


@pytest.fixture
def state_path(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "SETTINGS", dataclasses.replace(
        pipeline.SETTINGS, metadata_dir=tmp_path / "metadata",
    ))
    return pipeline._state_path()


def test_missing_state_supports_first_run(state_path):
    assert pipeline._read_state() == {"api_watermarks": {}, "processed_file_batches": []}
    assert not state_path.exists()


@pytest.mark.parametrize("content", [
    "{broken", "[]", '{"api_watermarks": []}',
    '{"api_watermarks": {"orders": "bad-date"}}',
    '{"processed_file_batches": "batch"}', '{"processed_file_batches": [null]}',
])
def test_invalid_state_fails_closed_without_overwriting(state_path, content):
    state_path.parent.mkdir()
    state_path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        pipeline._read_state()
    assert state_path.read_text(encoding="utf-8") == content


def test_failed_atomic_replace_preserves_old_bytes_and_cleans_temp(state_path, monkeypatch):
    pipeline._write_state({"last_run_id": "old"})
    before = state_path.read_bytes()

    def fail(*args):
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(type(state_path), "replace", fail)
    with pytest.raises(OSError, match="replacement failure"):
        pipeline._write_state({"last_run_id": "new"})
    assert state_path.read_bytes() == before
    assert list(state_path.parent.iterdir()) == [state_path]


def test_watermark_falls_back_per_row_and_compares_utc_instants():
    frame = pd.DataFrame({
        "updated_at": ["2026-07-01T09:00:00+07:00", None, "invalid"],
        "created_at": ["2026-08-01T00:00:00Z", "2026-07-02T00:00:00Z", "2026-07-03T00:00:00Z"],
    })
    assert pipeline._watermark(frame) == "2026-07-03T00:00:00+00:00"
    assert pipeline._watermark(pd.DataFrame()) is None
