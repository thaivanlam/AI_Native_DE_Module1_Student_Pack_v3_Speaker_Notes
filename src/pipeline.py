"""Command-line orchestration for the daily data pipeline."""
import argparse
import json
import logging
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_INPUT_DIR = Path("data/incremental/day_2026-07-01")


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI without importing optional ETL/database dependencies."""
    parser = argparse.ArgumentParser(description="Điều phối daily data pipeline")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR.as_posix(), help=f"Thư mục dữ liệu file theo ngày (mặc định: {DEFAULT_INPUT_DIR.as_posix()})")
    parser.add_argument("--source", choices=["file", "api", "both"], default="file", help="Nguồn dữ liệu (mặc định: file)")
    parser.add_argument("--refresh-mart", action="store_true", help="Làm mới Sales Data Mart sau khi nạp Core")
    parser.add_argument("--skip-processed-file", action="store_true", help="Bỏ qua file batch đã xử lý thành công")
    return parser


# `--help` is an interface contract and should remain usable on a machine that
# has not installed the pipeline's database/ETL libraries yet.
if __name__ == "__main__" and {"--help", "-h"}.intersection(sys.argv[1:]):
    _build_parser().parse_args()


import pandas as pd

from src.api_client import fetch_all_pages
from src.config import SETTINGS
from src.extract_files import read_dataset
from src.load_postgres import upsert_dataframe
from src.logger import get_logger
from src.quality_report import build_report
from src.transform import normalize
from src.validators import business_validator, integrity_validator, schema_validator

log = get_logger("pipeline")


class _RunLogger(logging.LoggerAdapter):
    """Attach the same run identifier to every orchestration message."""

    def process(self, msg, kwargs):
        return f"{msg} | run_id={self.extra['run_id']}", kwargs


API_RESOURCES = ("customers", "products", "orders", "order_items", "payments")
MASTER_RESOURCES = ("customers", "products")
TRANSACTION_RESOURCES = ("orders", "order_items", "payments")
DATA_FILES = schema_validator.DATA_FILES
CORE_COLUMN_RENAMES = {"orders": {"status": "order_status"}}


def new_run_id() -> str:
    """Use an opaque UUID so run artefacts cannot collide."""
    return str(uuid.uuid4())


def _state_path() -> Path:
    return SETTINGS.metadata_dir / "pipeline_state.json"


def _read_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {"api_watermarks": {}, "processed_file_batches": []}
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError(f"Invalid state file: {path}")
    state.setdefault("api_watermarks", {})
    state.setdefault("processed_file_batches", [])
    if not isinstance(state["api_watermarks"], dict):
        raise ValueError(f"Invalid api_watermarks in state file: {path}")
    for name, value in state["api_watermarks"].items():
        if not isinstance(value, str) or pd.isna(pd.to_datetime(value, errors="coerce", utc=True)):
            raise ValueError(f"Invalid API watermark for {name}: {value!r}")
    batches = state["processed_file_batches"]
    if not isinstance(batches, list) or not all(isinstance(item, str) for item in batches):
        raise ValueError(f"Invalid processed_file_batches in state file: {path}")
    return state


def _write_state(state: dict) -> Path:
    """Replace checkpoint atomically; caller invokes this only on success."""
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def save_raw(resource: str, rows: list, run_id: str, updated_after: str | None = None) -> Path:
    target = SETTINGS.raw_dir / run_id / f"{resource}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"resource": resource, "run_id": run_id,
               "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "updated_after": updated_after, "total": len(rows), "data": rows}
    # Exclusive creation makes a RAW payload immutable.
    with target.open("x", encoding="utf-8") as raw_file:
        json.dump(payload, raw_file, ensure_ascii=False, indent=2)
    log.info("RAW saved resource=%s rows=%d run_id=%s -> %s", resource, len(rows), run_id, target)
    return target


def extract_api_to_raw(run_id=None, resources=API_RESOURCES, updated_after=None, page_size=100) -> dict:
    run_id = run_id or new_run_id()
    files = {}
    for resource in resources:
        files[resource] = save_raw(resource, fetch_all_pages(resource, updated_after, page_size), run_id, updated_after)
    return files


def load_raw_to_core(run_id: str, resources=API_RESOURCES) -> dict:
    stats = {}
    for resource in resources:
        df = normalize(read_dataset(SETTINGS.raw_dir / run_id / f"{resource}.json"))
        stats[resource] = upsert_dataframe(resource, df.rename(columns=CORE_COLUMN_RENAMES.get(resource, {})))
    return stats


def _file_frames(input_dir: Path, resources=API_RESOURCES) -> dict[str, pd.DataFrame]:
    """Read only the requested file datasets (master data in hybrid mode)."""
    return {name: read_dataset(Path(input_dir) / DATA_FILES[name]) for name in resources}


def _api_frames(run_id: str, state: dict, resources=API_RESOURCES) -> dict[str, pd.DataFrame]:
    frames = {}
    for name in resources:
        watermark = state.get("api_watermarks", {}).get(name)
        rows = fetch_all_pages(name, updated_after=watermark, page_size=100)
        raw = save_raw(name, rows, run_id, watermark)
        # A successful incremental request can contain no new records. Keep an
        # empty schema for downstream validators; the RAW snapshot stays empty.
        frames[name] = read_dataset(raw) if rows else pd.DataFrame(columns=schema_validator.REQUIRED[name])
    return frames


def _source_frames(input_dir: Path, source: str, run_id: str, state: dict) -> dict[str, pd.DataFrame]:
    if source == "file":
        frames = _file_frames(input_dir)
    elif source == "api":
        frames = _api_frames(run_id, state)
    elif source == "both":
        frames = _file_frames(input_dir, MASTER_RESOURCES)
        frames.update(_api_frames(run_id, state, TRANSACTION_RESOURCES))
    else:
        raise ValueError(f"Unsupported source: {source}")
    for name, frame in frames.items():
        dataset_source = "file" if source == "file" or (source == "both" and name in MASTER_RESOURCES) else "api"
        log.info("Ingested source=%s dataset=%s rows=%d run_id=%s", dataset_source, name, len(frame), run_id)
    return frames


def _split_duplicate_pk(name: str, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pk = schema_validator.ID_COLUMN[name]
    duplicate = df.duplicated(subset=[pk], keep="first")
    rejected = df.loc[duplicate].copy()
    if not rejected.empty:
        rejected["error_code"] = "DUPLICATE_PRIMARY_KEY"
    return df.loc[~duplicate].copy(), rejected


def _references_for(frames: dict[str, pd.DataFrame]) -> tuple[dict, dict]:
    references = integrity_validator.load_references()
    order_dates = integrity_validator.load_order_dates()
    for table, column in (("customers", "customer_id"), ("products", "product_id"), ("orders", "order_id")):
        if column in frames[table]:
            references.setdefault(table, set()).update(frames[table][column].dropna().astype(str))
    if {"order_id", "order_date"}.issubset(frames["orders"].columns):
        order_dates.update(dict(zip(frames["orders"]["order_id"], frames["orders"]["order_date"])))
    return references, order_dates


def _write_rejects(run_id: str, name: str, rejected: pd.DataFrame) -> Path | None:
    if rejected.empty:
        return None
    target = SETTINGS.root / "data" / "rejected" / run_id / f"{name}_reject.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    rejected.to_csv(target, index=False)
    return target


def _watermark(df: pd.DataFrame) -> str | None:
    """Prefer each row's updated_at, falling back to its created_at."""
    values = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    for column in ("updated_at", "created_at"):
        if column in df:
            values = values.fillna(pd.to_datetime(df[column], errors="coerce", utc=True, format="mixed"))
    return values.max().isoformat() if values.notna().any() else None


def run(input_dir=DEFAULT_INPUT_DIR, source="file", refresh_mart=False, skip_processed_file=False, *, run_id=None) -> dict:
    """Run the eight ordered stages; errors propagate so the entrypoint exits 1."""
    input_dir, run_id = Path(input_dir), run_id or new_run_id()
    run_log = _RunLogger(log, {"run_id": run_id})
    run_log.info("[1/8] Khởi tạo")
    state = _read_state()
    resolved_input = str(input_dir.resolve())
    skip_file = skip_processed_file and resolved_input in state["processed_file_batches"]
    if source == "file" and skip_file:
        run_log.info("File batch already processed; SKIPPED | input_dir=%s", resolved_input)
        return {"run_id": run_id, "status": "skipped"}

    run_log.info("[2/8] Trích xuất | source=%s", source)
    if source == "both" and skip_file:
        run_log.info("File batch already processed; SKIPPED | input_dir=%s; continuing API", resolved_input)
        frames = {name: pd.DataFrame(columns=schema_validator.REQUIRED[name]) for name in MASTER_RESOURCES}
        frames.update(_api_frames(run_id, state, TRANSACTION_RESOURCES))
    else:
        frames = _source_frames(input_dir, source, run_id, state)
    run_log.info("[3/8] Chuẩn hóa & Schema")
    normalized = {}
    for name in API_RESOURCES:
        frame = normalize(frames[name]).rename(columns=CORE_COLUMN_RENAMES.get(name, {}))
        schema_validator.validate_schema(name, frame.rename(columns={"order_status": "status"}) if name == "orders" else frame)
        normalized[name] = frame

    run_log.info("[4/8] Kiểm tra Chất lượng")
    references, order_dates = _references_for(frames)
    prepared, report_rows = {}, []
    for name in API_RESOURCES:
        original = normalized[name]
        check = original.rename(columns={"order_status": "status"}) if name == "orders" else original
        business_valid, business_reject = business_validator.split_valid_invalid(name, check)
        unique_valid, duplicate_reject = _split_duplicate_pk(name, business_valid)
        valid, integrity_reject = integrity_validator.split_cross_table_invalid(name, unique_valid, references, order_dates)
        rejected = pd.concat([business_reject, duplicate_reject, integrity_reject], ignore_index=True)
        if name == "orders":
            valid, rejected = valid.rename(columns={"status": "order_status"}), rejected.rename(columns={"status": "order_status"})
        assert len(original) == len(valid) + len(rejected), f"Invariant violated for {name}"
        prepared[name] = (valid, rejected, len(original))

    run_log.info("[5/8] Nạp Core Database")
    load_stats = {}
    for name in API_RESOURCES:
        valid, rejected, incoming = prepared[name]
        reject_file = _write_rejects(run_id, name, rejected)
        load_stats[name] = upsert_dataframe(name, valid)
        stats = load_stats[name]
        run_log.info("[5/8] dataset=%s input=%d valid=%d reject=%d inserted=%d updated=%d%s", name, incoming, len(valid), len(rejected), stats["inserted"], stats["updated"], f" reject_file={reject_file}" if reject_file else "")
        report_rows.append({"dataset": name, "input": incoming, "valid": len(valid), "rejected": len(rejected)})

    run_log.info("[6/8] Đối soát & Báo cáo")
    for row in report_rows:
        assert row["input"] == row["valid"] + row["rejected"], (
            f"Invariant violated for {row['dataset']}: "
            f"{row['input']} != {row['valid']} + {row['rejected']}"
        )
        run_log.info("[6/8] dataset=%s %d = %d + %d OK", row["dataset"], row["input"], row["valid"], row["rejected"])
    build_report(report_rows, run_id=run_id, out_dir=SETTINGS.report_dir)

    run_log.info("[7/8] Làm mới Data Mart")
    if refresh_mart:
        from src.refresh_mart import refresh_mart
        refresh_mart()
        run_log.info("[7/8] Làm mới Data Mart OK")
    else:
        run_log.info("[7/8] Làm mới Data Mart SKIPPED")

    run_log.info("[8/8] Cập nhật Checkpoint")
    new_state = {"last_run_id": run_id, "last_successful_at": datetime.now(timezone.utc).isoformat(), "last_source": source, "status": "success", "api_watermarks": dict(state["api_watermarks"]), "processed_file_batches": list(state["processed_file_batches"])}
    if source in {"api", "both"}:
        for name, (valid, _, _) in prepared.items():
            if source == "both" and name in MASTER_RESOURCES:
                continue
            if value := _watermark(valid):
                previous = new_state["api_watermarks"].get(name)
                if previous is None or pd.Timestamp(value) > pd.Timestamp(previous):
                    new_state["api_watermarks"][name] = value
    if source in {"file", "both"} and resolved_input not in new_state["processed_file_batches"]:
        new_state["processed_file_batches"].append(resolved_input)
    _write_state(new_state)
    run_log.info("[8/8] Cập nhật Checkpoint State OK")
    return {"run_id": run_id, "status": "success", "datasets": report_rows, "load_stats": load_stats}


def parse_args(argv=None) -> argparse.Namespace:
    return _build_parser().parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    run_id = new_run_id()
    try:
        result = run(args.input_dir, args.source, args.refresh_mart, args.skip_processed_file, run_id=run_id)
    except Exception as exc:
        log.exception("[ALERT] Pipeline failed (exit 1) | run_id=%s error_type=%s message=%s", run_id, type(exc).__name__, str(exc).splitlines()[0] if str(exc) else "")
        return 1
    log.info("Pipeline hoàn thành (exit 0) | run_id=%s status=%s", run_id, result["status"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
