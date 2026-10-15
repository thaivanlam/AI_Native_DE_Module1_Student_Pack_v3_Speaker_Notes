"""Bai 1: Schema & Completeness Validation.

Data Quality Firewall - tang 1: kiem tra cau truc (schema) va do day du
(completeness) cua 5 bang theo Data Contract, cham diem chat luong tung dong.
"""
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / 'data' / 'dirty' / 'day_2026-07-02'
EVIDENCE_FILE = BASE_DIR / 'docs' / 'evidence' / '07-schema.txt'

MISSING_REQUIRED = 'MISSING_REQUIRED'

# Cột bắt buộc theo Data Contract (docs/data_contract.md)
REQUIRED = {
    'customers': ['customer_id', 'full_name', 'email', 'status'],
    'products': ['product_id', 'category_id', 'product_name', 'unit_price', 'status'],
    'orders': ['order_id', 'customer_id', 'order_date', 'status', 'order_total'],
    'order_items': ['order_item_id', 'order_id', 'product_id', 'quantity', 'unit_price', 'discount_amount'],
    'payments': ['payment_id', 'order_id', 'payment_date', 'payment_status', 'amount'],
}

# Trường bắt buộc phải có giá trị (không NULL, không chuỗi rỗng)
REQUIRED_VALUES = REQUIRED

# Cột khóa chính dùng làm row_id trong log
ID_COLUMN = {
    'customers': 'customer_id',
    'products': 'product_id',
    'orders': 'order_id',
    'order_items': 'order_item_id',
    'payments': 'payment_id',
}

DATA_FILES = {
    'customers': 'customers_daily.csv',
    'products': 'products_daily.csv',
    'orders': 'orders_daily.csv',
    'order_items': 'order_items_daily.csv',
    'payments': 'payments_daily.json',
}


def validate_schema(name, df):
    """Kiểm tra danh sách cột bắt buộc của dataset. Trả về True nếu đủ cột.

    Raises:
        ValueError: nếu thiếu cột cấu trúc, kèm tên dataset và cột thiếu.
    """
    required = REQUIRED[name]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f'dataset={name} thiếu cột bắt buộc theo Data Contract: {missing}')
    return True


def is_missing(value):
    """NULL (NaN/None/NaT) hoặc chuỗi rỗng đều tính là missing."""
    return pd.isna(value) or (isinstance(value, str) and value.strip() == '')


def score_rows(name, df):
    """Chấm điểm từng dòng (0-100): tỷ lệ trường REQUIRED_VALUES hợp lệ.

    Trả về DataFrame gồm: row_id, score, errors, missing_cols.
    """
    required = REQUIRED_VALUES[name]
    id_col = ID_COLUMN[name]
    records = []
    for _, row in df.iterrows():
        miss = [c for c in required if is_missing(row[c])]
        score = round(100 * (len(required) - len(miss)) / len(required))
        records.append({
            'row_id': row[id_col],
            'score': score,
            'errors': [MISSING_REQUIRED] if miss else [],
            'missing_cols': miss,
        })
    return pd.DataFrame(records)


def format_errors(errors):
    return '[' + ', '.join(errors) + ']'


def load_dataset(name):
    path = DATA_DIR / DATA_FILES[name]
    if path.suffix == '.json':
        return pd.read_json(path)
    return pd.read_csv(path)


def run(evidence_file=EVIDENCE_FILE, head=10):
    """Chạy validation trên toàn bộ dataset, in log và ghi minh chứng."""
    lines = []
    for name in REQUIRED:
        df = load_dataset(name)
        validate_schema(name, df)  # ValueError nếu thiếu cột cấu trúc

        scored = score_rows(name, df)
        n_bad = (scored['score'] < 100).sum()
        lines.append(f'== {name} ==')
        lines.append(f'file={DATA_FILES[name]} rows={len(df)} '
                     f'required_cols={len(REQUIRED[name])} thiếu cột: không')
        lines.append(f'rows có missing value: {n_bad}/{len(df)}')
        for _, r in scored.head(head).iterrows():
            lines.append(f'row_id={r.row_id} score={r.score} '
                         f'errors={format_errors(r.errors)}')
            if r.missing_cols:
                lines.append(f'  -> missing_cols={r.missing_cols}')
        lines.append('')

    output = '\n'.join(lines)
    print(output)
    Path(evidence_file).parent.mkdir(parents=True, exist_ok=True)
    Path(evidence_file).write_text(output + '\n', encoding='utf-8')
    print(f'[OK] Evidence ghi tại: {evidence_file}')


if __name__ == '__main__':
    run()
