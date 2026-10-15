"""Bài 4: Data Quality Report & Invariant Reconciliation.

Tổng hợp kết quả 3 tầng Data Quality Firewall (Schema -> Business -> Integrity),
xuất báo cáo CSV/JSON và kiểm tra bất biến Input = Valid + Rejected bằng assert.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.validators import business_validator, integrity_validator, schema_validator

EVIDENCE_FILE = schema_validator.EVIDENCE_FILE.parent / '07-invariant.txt'


def collect_stats():
    """Chạy 3 tầng validator trên từng dataset, trả về list chỉ số.

    Mỗi tầng tách df thành 2 phần rời nhau, nên Input = Valid + Rejected
    luôn được bảo toàn qua các tầng.
    """
    reference_ids = integrity_validator.load_references()
    order_dates = integrity_validator.load_order_dates()

    stats = []
    for name in schema_validator.REQUIRED:
        df = schema_validator.load_dataset(name)
        schema_validator.validate_schema(name, df)  # Tầng 1: Schema (abort nếu thiếu cột)

        valid_df, rejected_b = business_validator.split_valid_invalid(name, df)  # Tầng 2: Business

        valid_df, rejected_i = integrity_validator.split_cross_table_invalid(  # Tầng 3: Integrity
            name, valid_df, reference_ids, order_dates)

        row = {
            'dataset': name,
            'input': len(df),
            'valid': len(valid_df),
            'rejected': len(rejected_b) + len(rejected_i),
        }
        assert row['input'] == row['valid'] + row['rejected'], (
            f"Invariant violated cho {name}: "
            f"{row['input']} != {row['valid']} + {row['rejected']}")
        stats.append(row)
    return stats


def build_report(stats, run_id=None, out_dir='reports'):
    """Lưu báo cáo CSV + JSON và kiểm tra bất biến Input = Valid + Rejected."""
    out_path = Path(out_dir)
    if not out_path.is_absolute():
        out_path = schema_validator.BASE_DIR / out_path
    out_path.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(stats, columns=['dataset', 'input', 'valid', 'rejected'])
    for row in stats:
        assert row['input'] == row['valid'] + row['rejected'], (
            f"Invariant violated cho {row['dataset']}: "
            f"{row['input']} != {row['valid']} + {row['rejected']}")

    csv_file = out_path / 'data_quality_report.csv'
    df.to_csv(csv_file, index=False)

    total = {key: int(df[key].sum()) for key in ('input', 'valid', 'rejected')}
    assert total['input'] == total['valid'] + total['rejected'], (
        f"Invariant violated tổng thể: {total['input']} != "
        f"{total['valid']} + {total['rejected']}")

    summary = {
        'run_id': run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        'data_dir': str(schema_validator.DATA_DIR),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'invariant': 'input = valid + rejected',
        'invariant_ok': True,
        'total': total,
        'datasets': stats,
    }
    json_file = out_path / 'data_quality_summary.json'
    json_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n',
                         encoding='utf-8')
    return df, csv_file, json_file


def run():
    """Chạy toàn pipeline report và ghi log minh chứng invariant."""
    stats = collect_stats()
    df, csv_file, json_file = build_report(stats)

    lines = [f'== Data Quality Report & Invariant — {schema_validator.DATA_DIR} ==']
    for row in stats:
        lines.append(f"{row['dataset']}: {row['input']} = "
                     f"{row['valid']} + {row['rejected']} OK")
    total = df[['input', 'valid', 'rejected']].sum()
    lines.append(f"TOTAL: {total['input']} = {total['valid']} + {total['rejected']} OK")
    lines.append('INVARIANT Input = Valid + Rejected: PASS (assert passed)')
    lines.append(f'report_csv={csv_file}')
    lines.append(f'report_json={json_file}')

    output = '\n'.join(lines)
    print(output)
    EVIDENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_FILE.write_text(output + '\n', encoding='utf-8')
    print(f'\n[OK] Evidence ghi tại: {EVIDENCE_FILE}')


if __name__ == '__main__':
    run()
