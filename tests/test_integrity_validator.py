import pandas as pd
import pytest

from src.validators import integrity_validator as integrity


@pytest.mark.parametrize('name,column,table,code', [
    (name, column, table, code)
    for name, rules in integrity.FK_RULES.items()
    for column, table, code in rules
])
def test_foreign_keys(name, column, table, code):
    frame = pd.DataFrame({column: ['known', 'orphan']}, index=[9, 9])
    original = frame.copy(deep=True)
    valid, rejected = integrity.split_cross_table_invalid(
        name, frame, {table: {'known'}}, {})
    assert valid[column].tolist() == ['known']
    assert rejected['error_code'].tolist() == [code]
    assert valid.index.tolist() == rejected.index.tolist() == [9]
    pd.testing.assert_frame_equal(frame, original)


def test_multiple_foreign_key_errors():
    frame = pd.DataFrame({'order_id': ['missing'], 'product_id': ['missing']})
    valid, rejected = integrity.split_cross_table_invalid('order_items', frame, {}, {})
    assert valid.empty
    assert rejected.error_code.tolist() == ['FK_ORDER_NOT_FOUND|FK_PRODUCT_NOT_FOUND']


def test_chronology_boundaries_and_timezones():
    frame = pd.DataFrame({
        'order_id': [' O1 '] * 4 + ['orphan'],
        'payment_date': ['2026-07-02T08:59:59+07:00',
                         '2026-07-02T02:00:00Z',
                         '2026-07-02T09:00:01+07:00', 'invalid',
                         '2026-07-01T00:00:00Z'],
    })
    valid, rejected = integrity.split_cross_table_invalid(
        'payments', frame, {'orders': {'O1'}},
        {'O1': '2026-07-02T09:00:00+07:00'})
    assert valid.index.tolist() == [1, 2, 3]
    assert rejected.error_code.tolist() == ['PAYMENT_BEFORE_ORDER', 'FK_ORDER_NOT_FOUND']
    assert len(frame) == len(valid) + len(rejected)


def test_two_argument_call_loads_references(monkeypatch):
    monkeypatch.setattr(integrity, 'load_references', lambda: {'orders': {'O1'}})
    monkeypatch.setattr(integrity, 'load_order_dates', lambda: {'O1': '2026-07-02'})
    frame = pd.DataFrame({'order_id': ['O1'], 'payment_date': ['2026-07-01']})
    valid, rejected = integrity.split_cross_table_invalid('payments', frame)
    assert valid.empty
    assert rejected.error_code.tolist() == ['PAYMENT_BEFORE_ORDER']


def test_empty_input():
    frame = pd.DataFrame(columns=['order_id', 'payment_date'])
    valid, rejected = integrity.split_cross_table_invalid('payments', frame, {}, {})
    pd.testing.assert_frame_equal(valid, frame)
    assert rejected.empty
    assert 'error_code' in rejected.columns
