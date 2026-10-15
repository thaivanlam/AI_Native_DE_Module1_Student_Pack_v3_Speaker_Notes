"""Bài 3: Cross-Table Integrity & Chronology.

Data Quality Firewall - tầng 3: kiểm tra khóa ngoại (4 cặp FK) và
tính thứ tự thời gian payment_date >= order_date.
"""
from pathlib import Path

import pandas as pd

from src.validators import schema_validator

SEED_DIR = schema_validator.BASE_DIR / 'data' / 'seed'
CHRONOLOGY_CODE = 'PAYMENT_BEFORE_ORDER'

# FK: (cột trong df, bảng tham chiếu, error_code)
FK_RULES = {
    'products': [('category_id', 'categories', 'FK_CATEGORY_NOT_FOUND')],
    'orders': [('customer_id', 'customers', 'FK_CUSTOMER_NOT_FOUND')],
    'order_items': [
        ('order_id', 'orders', 'FK_ORDER_NOT_FOUND'),
        ('product_id', 'products', 'FK_PRODUCT_NOT_FOUND'),
    ],
    'payments': [('order_id', 'orders', 'FK_ORDER_NOT_FOUND')],
}


def split_cross_table_invalid(name, df, reference_ids=None, order_dates=None):
    """Tách df thành (valid_df, rejected_df) theo FK và chronology.

    Args:
        name: tên bảng.
        df: DataFrame cần kiểm tra.
        reference_ids: dict {bảng tham chiếu: set id hợp lệ}.
        order_dates: dict {order_id: order_date} cho chronology check.
    """
    reference_ids = reference_ids or {}
    order_dates = order_dates or {}
    errors = [[] for _ in range(len(df))]

    # 1. Foreign Key checks
    for col, ref_table, code in FK_RULES.get(name, []):
        valid_ids = reference_ids.get(ref_table, set())
        if col not in df.columns:
            continue
        for i, value in enumerate(df[col]):
            if schema_validator.is_missing(value):
                continue
            if str(value).strip() not in valid_ids:
                errors[i].append(code)

    # 2. Chronology: payment_date >= order_date, vi phạm nếu payment trước order
    if name == 'payments' and {'payment_date', 'order_id'} <= set(df.columns):
        payment_dates = pd.to_datetime(df['payment_date'], errors='coerce',
                                       format='ISO8601')
        order_dates_series = pd.to_datetime(
            df['order_id'].map(order_dates), errors='coerce', format='ISO8601')
        for i in range(len(df)):
            if (pd.notna(payment_dates[i]) and pd.notna(order_dates_series[i])
                    and payment_dates[i] < order_dates_series[i]):
                errors[i].append(CHRONOLOGY_CODE)

    df = df.copy()
    df['error_code'] = ['|'.join(row_errors) for row_errors in errors]
    rejected_df = df[df['error_code'] != '']
    valid_df = df[df['error_code'] == ''].drop(columns=['error_code'])
    return valid_df, rejected_df


def load_references():
    """Tập id hợp lệ: seed (kho lịch sử) gộp với file dirty của ngày."""
    reference_ids = {
        'categories': set(pd.read_csv(SEED_DIR / 'categories.csv')['category_id']),
        'customers': set(pd.read_csv(SEED_DIR / 'customers.csv')['customer_id']),
        'orders': set(pd.read_csv(SEED_DIR / 'orders.csv')['order_id']),
        'products': set(pd.read_csv(SEED_DIR / 'products.csv')['product_id']),
    }
    daily_columns = {'customers': 'customer_id', 'orders': 'order_id',
                     'products': 'product_id'}
    for table, col in daily_columns.items():
        reference_ids[table] |= set(schema_validator.load_dataset(table)[col].dropna())
    return reference_ids


def load_order_dates():
    orders = pd.concat([
        pd.read_csv(SEED_DIR / 'orders.csv')[['order_id', 'order_date']],
        schema_validator.load_dataset('orders')[['order_id', 'order_date']],
    ])
    return dict(zip(orders['order_id'], orders['order_date']))


def run(evidence_file=schema_validator.EVIDENCE_FILE.parent / '07-integrity.txt'):
    """Chạy cross-table integrity trên dirty data, ghi danh sách vi phạm."""
    reference_ids = load_references()
    order_dates = load_order_dates()

    lines = [f'== Cross-Table Integrity & Chronology — {schema_validator.DATA_DIR} ==']
    for name in ['products', 'orders', 'order_items', 'payments']:
        df = schema_validator.load_dataset(name)
        valid_df, rejected_df = split_cross_table_invalid(
            name, df, reference_ids, order_dates)
        lines.append(f'{name}: valid={len(valid_df)} rejected={len(rejected_df)}')
        for _, row in rejected_df.iterrows():
            pk = row[schema_validator.ID_COLUMN[name]]
            for col, ref_table, code in FK_RULES.get(name, []):
                value = row[col]
                if schema_validator.is_missing(value):
                    continue
                if str(value).strip() not in reference_ids[ref_table]:
                    lines.append(f'{name} id={pk} {col}={value} NOT FOUND ({code})')
            if name == 'payments' and CHRONOLOGY_CODE in str(row['error_code']):
                lines.append(f'{name} id={row["payment_id"]} '
                             f'payment_date={row["payment_date"]} < '
                             f'order_date={order_dates.get(row["order_id"])} '
                             f'({CHRONOLOGY_CODE})')
        lines.append('')

    output = '\n'.join(lines)
    print(output)
    Path(evidence_file).parent.mkdir(parents=True, exist_ok=True)
    Path(evidence_file).write_text(output + '\n', encoding='utf-8')
    print(f'[OK] Evidence ghi tại: {evidence_file}')


if __name__ == '__main__':
    run()
