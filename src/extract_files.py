import codecs
import json
from pathlib import Path

import pandas as pd


def _detect_encoding(path: Path) -> str:
    with path.open("rb") as f:
        has_bom = f.read(3) == codecs.BOM_UTF8
    return "utf-8-sig" if has_bom else "utf-8"


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding=_detect_encoding(path))
    except pd.errors.EmptyDataError:
        raise ValueError(f"Empty dataset: {path}") from None


def _read_json(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding=_detect_encoding(path)))
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    if not isinstance(payload, list):
        raise ValueError(f"Unsupported JSON structure: {path}")
    return pd.DataFrame(payload)


def read_dataset(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = _read_csv(path)
    elif suffix == ".json":
        df = _read_json(path)
    else:
        raise ValueError(f"Unsupported file: {path}")

    if len(df) == 0:
        raise ValueError(f"Empty dataset: {path}")
    return df


def profile(df: pd.DataFrame) -> dict:
    return {
        "rows": len(df),
        "columns": list(df.columns),
        "missing": {col: int(n) for col, n in df.isna().sum().items()},
        "duplicates": int(df.duplicated().sum()),
    }
