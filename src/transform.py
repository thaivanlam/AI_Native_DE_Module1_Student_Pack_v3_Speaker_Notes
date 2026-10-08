import pandas as pd

LOWERCASE_COLUMNS = ("email", "status", "payment_status", "payment_method", "channel")
NUMERIC_COLUMNS = (
    "unit_price",
    "cost_price",
    "order_total",
    "discount_amount",
    "amount",
    "quantity",
)
TIMESTAMP_SUFFIXES = ("_at", "_date")


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _lower(value):
    return value.lower() if isinstance(value, str) else value


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out.columns = [c.strip().lower() for c in out.columns]

    for col in out.select_dtypes(include=["object", "string"]).columns:
        out[col] = out[col].map(_strip)

    for col in LOWERCASE_COLUMNS:
        if col in out.columns:
            out[col] = out[col].map(_lower)

    for col in NUMERIC_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    for col in out.columns:
        if col.endswith(TIMESTAMP_SUFFIXES):
            out[col] = pd.to_datetime(out[col], errors="coerce", utc=True)

    return out
