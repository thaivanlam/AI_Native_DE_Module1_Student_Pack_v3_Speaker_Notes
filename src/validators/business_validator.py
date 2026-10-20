"""Bài 2: Business Rules Validation — các quy tắc cấp dòng (row-level rules).

Data Quality Firewall - tầng 2: email hợp lệ, enum theo Data Contract,
range tiền/số lượng không âm, consistency discount <= gross.
"""
import re
from pathlib import Path

import pandas as pd

from src.validators import schema_validator

EMAIL_REGEX = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
EMAIL_CODE = 'INVALID_EMAIL'
CONSISTENCY_CODE = 'DISCOUNT_EXCEEDS_GROSS'

# Enum theo Data Contract, riêng cho từng bảng (cột 'status' nghĩa khác nhau)
ENUM_RULES = {
    'customers': {'status': ['active', 'inactive']},
    'products': {'status': ['active', 'inactive', 'discontinued']},
    'orders': {
        'status': ['pending', 'confirmed', 'shipped', 'completed', 'cancelled'],
        'channel': ['web', 'mobile_app', 'social'],
    },
    'payments': {
        'payment_status': ['pending', 'success', 'failed', 'refunded'],
        'payment_method': ['cash', 'bank_transfer', 'card', 'e_wallet'],
    },
}

# Range: (cột, error_code, 'non_neg' = v < 0 vi phạm | 'pos' = v <= 0 vi phạm)
RANGE_RULES = {
    'products': [('unit_price', 'NEGATIVE_PRICE', 'non_neg')],
    'orders': [('order_total', 'NEGATIVE_ORDER_TOTAL', 'non_neg')],
    'order_items': [
        ('unit_price', 'NEGATIVE_PRICE', 'non_neg'),
        ('quantity', 'INVALID_QUANTITY', 'pos'),
        ('discount_amount', 'NEGATIVE_DISCOUNT', 'non_neg'),
    ],
    'payments': [('amount', 'NEGATIVE_AMOUNT', 'non_neg')],
}


def _is_blank(value):
    return pd.isna(value) or (isinstance(value, str) and value.strip() == '')


def _row_errors(name, df):
    """Trả về list error_code (list của list) cho từng dòng của df."""
    errors = [[] for _ in range(len(df))]

    # 1. Email hợp lệ (chỉ bảng customers)
    if name == 'customers' and 'email' in df.columns:
        for i, value in enumerate(df['email']):
            if not _is_blank(value) and not re.fullmatch(EMAIL_REGEX, str(value).strip()):
                errors[i].append(EMAIL_CODE)

    # 2. Enum thuộc danh sách cho phép
    for col, allowed in ENUM_RULES.get(name, {}).items():
        if col not in df.columns:
            continue
        for i, value in enumerate(df[col]):
            if not _is_blank(value) and str(value).strip() not in allowed:
                errors[i].append(f'INVALID_{col.upper()}')

    # 3. Range: tiền không âm, số lượng > 0
    for col, code, kind in RANGE_RULES.get(name, []):
        if col not in df.columns:
            continue
        numeric = pd.to_numeric(df[col], errors='coerce')
        for i, value in enumerate(numeric):
            if pd.isna(value):
                continue
            if (kind == 'non_neg' and value < 0) or (kind == 'pos' and value <= 0):
                errors[i].append(code)

    # 4. Consistency: discount_amount <= quantity * unit_price
    cols = {'discount_amount', 'quantity', 'unit_price'}
    if name == 'order_items' and cols <= set(df.columns):
        discount = pd.to_numeric(df['discount_amount'], errors='coerce')
        gross = (pd.to_numeric(df['quantity'], errors='coerce')
                 * pd.to_numeric(df['unit_price'], errors='coerce'))
        for i in range(len(df)):
            if (pd.notna(discount.iloc[i]) and pd.notna(gross.iloc[i])
                    and discount.iloc[i] > gross.iloc[i]):
                errors[i].append(CONSISTENCY_CODE)

    return errors


def split_valid_invalid(name, df):
    """Tách df thành (valid_df, rejected_df) theo business rules.

    rejected_df có thêm cột error_code, nhiều lỗi nối bằng '|'.
    Giữ nguyên dữ liệu và index đầu vào. Missing value thuộc tầng schema;
    hàm này chỉ kiểm tra business rules trên các giá trị có mặt.
    """
    errors = _row_errors(name, df)
    df = df.copy()
    df['error_code'] = ['|'.join(row_errors) for row_errors in errors]
    rejected_df = df[df['error_code'] != '']
    valid_df = df[df['error_code'] == ''].drop(columns=['error_code'])
    return valid_df, rejected_df


def count_violations(rejected_df):
    """Đếm số dòng vi phạm cho từng error_code (mở rộng qua dấu '|')."""
    counts = {}
    for codes in rejected_df['error_code']:
        for code in codes.split('|'):
            counts[code] = counts.get(code, 0) + 1
    return counts


def run(evidence_file=schema_validator.EVIDENCE_FILE.parent / '07-business.txt'):
    """Chạy business rules trên toàn bộ dataset, ghi bảng đếm per-rule."""
    lines = [f'== Business Rules Validation — {schema_validator.DATA_DIR} ==']
    total = {}
    for name in schema_validator.REQUIRED:
        df = schema_validator.load_dataset(name)
        valid_df, rejected_df = split_valid_invalid(name, df)
        assert len(df) == len(valid_df) + len(rejected_df), name
        counts = count_violations(rejected_df)
        for code, n in counts.items():
            total[code] = total.get(code, 0) + n
        detail = ', '.join(f'{c}: {n}' for c, n in sorted(counts.items())) or '-'
        lines.append(f'{name}: valid={len(valid_df)} rejected={len(rejected_df)}')
        lines.append(f'  per-rule: {detail}')

    lines.append('')
    lines.append('PER-RULE VIOLATIONS (tổng 5 bảng):')
    for code, n in sorted(total.items(), key=lambda kv: -kv[1]):
        lines.append(f'{code}: {n}')

    output = '\n'.join(lines)
    print(output)
    Path(evidence_file).parent.mkdir(parents=True, exist_ok=True)
    Path(evidence_file).write_text(output + '\n', encoding='utf-8')
    print(f'\n[OK] Evidence ghi tại: {evidence_file}')


if __name__ == '__main__':
    run()
