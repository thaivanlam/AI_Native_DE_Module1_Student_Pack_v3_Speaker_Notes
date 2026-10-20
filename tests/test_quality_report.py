import json

import pandas as pd
import pytest

from src import quality_report


def test_report_exports_matching_csv_json(tmp_path):
    stats = [
        {'dataset': 'customers', 'input': 4, 'valid': 3, 'rejected': 1},
        {'dataset': 'orders', 'input': 2, 'valid': 0, 'rejected': 2},
    ]
    frame, csv_file, json_file = quality_report.build_report(
        iter(stats), run_id='test-run', out_dir=tmp_path)

    pd.testing.assert_frame_equal(pd.read_csv(csv_file), frame)
    summary = json.loads(json_file.read_text(encoding='utf-8'))
    assert summary['run_id'] == 'test-run'
    assert summary['datasets'] == stats
    assert summary['total'] == {'input': 6, 'valid': 3, 'rejected': 3}
    assert summary['invariant_ok'] is True


def test_each_dataset_must_balance_even_when_totals_balance(tmp_path):
    stats = [
        {'dataset': 'customers', 'input': 4, 'valid': 2, 'rejected': 1},
        {'dataset': 'orders', 'input': 2, 'valid': 2, 'rejected': 1},
    ]
    with pytest.raises(AssertionError, match='customers'):
        quality_report.build_report(stats, out_dir=tmp_path)
    assert not list(tmp_path.glob('data_quality_*'))


def test_empty_report(tmp_path):
    frame, csv_file, json_file = quality_report.build_report([], out_dir=tmp_path)
    assert frame.empty
    assert list(pd.read_csv(csv_file).columns) == ['dataset', 'input', 'valid', 'rejected']
    summary = json.loads(json_file.read_text(encoding='utf-8'))
    assert summary['total'] == {'input': 0, 'valid': 0, 'rejected': 0}


def test_collect_stats_rejects_missing_values_and_counts_rows_once(monkeypatch):
    schema = quality_report.schema_validator
    monkeypatch.setattr(schema, 'REQUIRED', {'customers': schema.REQUIRED['customers']})
    frame = pd.DataFrame([
        {'customer_id': 'C1', 'full_name': 'A', 'email': 'a@b.com', 'status': 'active'},
        {'customer_id': 'C2', 'full_name': ' ', 'email': 'b@b.com', 'status': 'active'},
        {'customer_id': 'C3', 'full_name': 'C', 'email': 'bad', 'status': 'wrong'},
        {'customer_id': 'C4', 'full_name': None, 'email': 'bad', 'status': 'wrong'},
    ], index=[7, 7, 7, 7])
    monkeypatch.setattr(schema, 'load_dataset', lambda name: frame)
    monkeypatch.setattr(quality_report.integrity_validator, 'load_references', lambda: {})
    monkeypatch.setattr(quality_report.integrity_validator, 'load_order_dates', lambda: {})

    assert quality_report.collect_stats() == [
        {'dataset': 'customers', 'input': 4, 'valid': 1, 'rejected': 3}]


def test_run_writes_invariant_evidence(tmp_path, monkeypatch):
    stats = [{'dataset': 'customers', 'input': 3, 'valid': 2, 'rejected': 1}]
    monkeypatch.setattr(quality_report, 'collect_stats', lambda: stats)
    monkeypatch.setattr(quality_report.schema_validator, 'BASE_DIR', tmp_path)
    evidence = tmp_path / 'evidence' / '07-invariant.txt'
    monkeypatch.setattr(quality_report, 'EVIDENCE_FILE', evidence)

    quality_report.run()

    log = evidence.read_text(encoding='utf-8')
    assert 'customers: 3 = 2 + 1 OK' in log
    assert 'TOTAL: 3 = 2 + 1 OK' in log
    assert 'PASS (assert passed)' in log
