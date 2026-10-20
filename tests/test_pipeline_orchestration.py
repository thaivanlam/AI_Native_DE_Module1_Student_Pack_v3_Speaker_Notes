"""Exercise orchestration with real validators/files and an isolated DB boundary."""
import dataclasses
import json
import os
import subprocess
import sys
import uuid

import pandas as pd
import pytest

from src import pipeline, refresh_mart


@pytest.fixture
def batch(tmp_path, monkeypatch):
    settings = dataclasses.replace(
        pipeline.SETTINGS, root=tmp_path, metadata_dir=tmp_path / "metadata",
        report_dir=tmp_path / "reports",
    )
    monkeypatch.setattr(pipeline, "SETTINGS", settings)
    customer = dict(customer_id="C1", full_name=" Test User ",
                    email=" TEST@EXAMPLE.COM ", status=" ACTIVE ")
    frames = {
        "customers": pd.DataFrame([
            customer, customer, dict(customer, customer_id="C2", email="bad-email"),
        ]),
        "products": pd.DataFrame([dict(product_id="P1", category_id="CAT1",
                                       product_name="Product", unit_price="10", status="active")]),
        "orders": pd.DataFrame([dict(order_id="O1", customer_id="C1", order_date="2026-07-01",
                                     status="completed", order_total="20")]),
        "order_items": pd.DataFrame([dict(order_item_id="I1", order_id="O1", product_id="P1",
                                          quantity="2", unit_price="10", discount_amount="0")]),
        "payments": pd.DataFrame([dict(payment_id="PAY1", order_id="O1", payment_date="2026-07-02",
                                       payment_status="success", amount="20")]),
    }
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    for name, filename in pipeline.DATA_FILES.items():
        path = input_dir / filename
        if path.suffix == ".json":
            frames[name].to_json(path, orient="records")
        else:
            frames[name].to_csv(path, index=False)
    monkeypatch.setattr(pipeline, "_references_for", lambda frames: (
        {"categories": {"CAT1"}, "customers": {"C1"}, "products": {"P1"}, "orders": {"O1"}},
        {"O1": "2026-07-01"},
    ))
    events = []

    def upsert(name, df):
        events.append((name, df.copy()))
        return {"inserted": len(df), "updated": 0}

    monkeypatch.setattr(pipeline, "upsert_dataframe", upsert)
    monkeypatch.setattr(refresh_mart, "refresh_mart", lambda: events.append(("mart", None)))
    state = {"api_watermarks": {"orders": "2026-06-30T00:00:00Z"},
             "processed_file_batches": [], "last_run_id": "previous-run"}
    pipeline._write_state(state)
    return input_dir, events, settings


def test_cli_defaults_and_all_flags():
    args = pipeline.parse_args([])
    assert (args.input_dir, args.source, args.refresh_mart, args.skip_processed_file) == (
        "data/incremental/day_2026-07-01", "file", False, False,
    )
    args = pipeline.parse_args(["--input-dir", "batch", "--source", "both",
                                "--refresh-mart", "--skip-processed-file"])
    assert (args.input_dir, args.source, args.refresh_mart, args.skip_processed_file) == (
        "batch", "both", True, True,
    )
    with pytest.raises(SystemExit) as exc:
        pipeline.parse_args(["--source", "unknown"])
    assert exc.value.code == 2


def test_help_works_without_site_packages():
    result = subprocess.run([sys.executable, "-S", "-m", "src.pipeline", "--help"],
                            capture_output=True, encoding="utf-8",
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert result.returncode == 0
    for flag in ("--input-dir", "--source", "--refresh-mart", "--skip-processed-file"):
        assert flag in result.stdout


@pytest.mark.parametrize("refresh", [False, True])
def test_success_loads_valid_rows_rejects_reports_then_checkpoints(batch, monkeypatch, refresh):
    input_dir, events, settings = batch
    before = pipeline._state_path().read_bytes()
    write_state = pipeline._write_state

    def checkpoint(state):
        assert pipeline._state_path().read_bytes() == before
        assert (settings.report_dir / "data_quality_summary.json").exists()
        assert [name for name, _ in events] == list(pipeline.API_RESOURCES) + (["mart"] if refresh else [])
        events.append(("checkpoint", None))
        return write_state(state)

    monkeypatch.setattr(pipeline, "_write_state", checkpoint)
    result = pipeline.run(input_dir, refresh_mart=refresh)
    uuid.UUID(result["run_id"])
    assert result["status"] == "success"
    customer = events[0][1].iloc[0]
    assert customer["full_name"] == "Test User"
    assert customer["email"] == "test@example.com"
    assert "order_status" in events[2][1] and "status" not in events[2][1]
    assert result["datasets"][0] == {"dataset": "customers", "input": 3, "valid": 1, "rejected": 2}
    rejects = pd.read_csv(settings.root / "data" / "rejected" / result["run_id"] / "customers_reject.csv")
    assert set(rejects["error_code"]) == {"INVALID_EMAIL", "DUPLICATE_PRIMARY_KEY"}
    summary = json.loads((settings.report_dir / "data_quality_summary.json").read_text())
    assert summary["run_id"] == result["run_id"] and summary["invariant_ok"]
    state = pipeline._read_state()
    assert state["last_run_id"] == result["run_id"]
    assert state["status"] == "success" and state["last_source"] == "file"
    assert state["processed_file_batches"] == [str(input_dir.resolve())]
    assert state["api_watermarks"] == {"orders": "2026-06-30T00:00:00Z"}
    assert events[-1][0] == "checkpoint"


@pytest.mark.parametrize("stage", ["extract", "schema", "quality", "load", "report", "mart"])
def test_failure_exits_one_and_keeps_checkpoint(batch, monkeypatch, stage):
    input_dir, events, _ = batch
    before = pipeline._state_path().read_bytes()

    def fail(*args, **kwargs):
        raise RuntimeError(f"Failed at {stage}")

    targets = {
        "extract": (pipeline, "_source_frames"),
        "schema": (pipeline.schema_validator, "validate_schema"),
        "quality": (pipeline.business_validator, "split_valid_invalid"),
        "load": (pipeline, "upsert_dataframe"),
        "report": (pipeline, "build_report"),
        "mart": (refresh_mart, "refresh_mart"),
    }
    monkeypatch.setattr(*targets[stage], fail)
    assert pipeline.main(["--input-dir", str(input_dir), "--refresh-mart"]) == 1
    assert pipeline._state_path().read_bytes() == before
    assert all(name != "mart" for name, _ in events)
    if stage in {"extract", "schema", "quality", "load"}:
        assert events == []


def test_count_mismatch_aborts_before_loading(batch, monkeypatch):
    input_dir, events, _ = batch
    before = pipeline._state_path().read_bytes()
    monkeypatch.setattr(pipeline, "_split_duplicate_pk", lambda name, df: (df, df))
    with pytest.raises(AssertionError, match="Invariant violated for customers"):
        pipeline.run(input_dir)
    assert events == []
    assert pipeline._state_path().read_bytes() == before


def test_skip_processed_file_does_not_load_or_rewrite_state(batch):
    input_dir, events, _ = batch
    pipeline.run(input_dir)
    before = pipeline._state_path().read_bytes()
    events.clear()
    assert pipeline.run(input_dir, skip_processed_file=True)["status"] == "skipped"
    assert events == []
    assert pipeline._state_path().read_bytes() == before


def test_main_logs_all_stages_and_run_id(batch, caplog, monkeypatch):
    input_dir, _, _ = batch
    monkeypatch.setattr(pipeline.log, "propagate", True)
    assert pipeline.main(["--input-dir", str(input_dir)]) == 0
    messages = [r.getMessage() for r in caplog.records if r.name == "pipeline"]
    run_id = pipeline._read_state()["last_run_id"]
    assert all(f"run_id={run_id}" in message for message in messages)
    for step in range(1, 9):
        assert any(f"[{step}/8]" in message for message in messages)
    assert any("SKIPPED" in message for message in messages)
    assert "exit 0" in messages[-1]
