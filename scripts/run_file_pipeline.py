"""Batch runner RAW -> STAGING: read_dataset -> profile -> normalize -> <dataset>_clean.csv."""
import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import SETTINGS
from src.extract_files import profile, read_dataset
from src.logger import get_logger
from src.transform import normalize

DEFAULT_INPUT_DIR = "data/incremental/day_2026-07-01"
DATASETS = {
    "customers": "customers_daily.csv",
    "products": "products_daily.csv",
    "orders": "orders_daily.csv",
    "order_items": "order_items_daily.csv",
    "payments": "payments_daily.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="File ingestion batch runner (RAW -> STAGING)")
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help=f"Thư mục batch đầu vào (mặc định: {DEFAULT_INPUT_DIR})",
    )
    return parser.parse_args()


def resolve_input_dir(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else SETTINGS.root / path


def checksums(input_dir: Path) -> dict:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(input_dir.iterdir())
        if p.is_file()
    }


def run(input_dir: Path) -> int:
    logger = get_logger()
    logger.info("Pipeline start | input_dir=%s | staging_dir=%s", input_dir, SETTINGS.staging_dir)

    if not input_dir.is_dir():
        logger.error("Input directory not found: %s", input_dir)
        return 1

    SETTINGS.staging_dir.mkdir(parents=True, exist_ok=True)
    before = checksums(input_dir)

    failed = []
    total_in = total_out = 0
    for dataset, filename in DATASETS.items():
        source = input_dir / filename
        try:
            raw = read_dataset(source)
        except (FileNotFoundError, ValueError):
            failed.append(dataset)
            logger.warning("Skip dataset=%s, continue with next dataset", dataset)
            continue

        stats = profile(raw)
        logger.info(
            "Profile dataset=%s rows=%d cols=%d missing_total=%d duplicates=%d",
            dataset,
            stats["rows"],
            len(stats["columns"]),
            sum(stats["missing"].values()),
            stats["duplicates"],
        )

        clean = normalize(raw)
        target = SETTINGS.staging_dir / f"{dataset}_clean.csv"
        clean.to_csv(target, index=False, encoding="utf-8")
        total_in += len(raw)
        total_out += len(clean)
        logger.info(
            "Staged dataset=%s rows_in=%d rows_out=%d -> %s",
            dataset,
            len(raw),
            len(clean),
            target.relative_to(SETTINGS.root).as_posix(),
        )

    raw_intact = checksums(input_dir) == before
    if raw_intact:
        logger.info("RAW check OK | %d input files unchanged (sha256)", len(before))
    else:
        logger.error("RAW check FAILED | input files changed during run: %s", input_dir)

    logger.info(
        "Pipeline end | datasets_ok=%d datasets_failed=%d rows_in=%d rows_out=%d",
        len(DATASETS) - len(failed),
        len(failed),
        total_in,
        total_out,
    )
    return 1 if failed or not raw_intact else 0


if __name__ == "__main__":
    sys.exit(run(resolve_input_dir(parse_args().input_dir)))
