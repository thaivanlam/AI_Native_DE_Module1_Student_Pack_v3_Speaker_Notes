import pandas as pd
import pytest

from src.validators import schema_validator as schema


@pytest.mark.parametrize('name', schema.REQUIRED)
def test_schema_reports_all_missing_columns(name):
    columns = schema.REQUIRED[name]
    frame = pd.DataFrame(columns=columns[2:])
    with pytest.raises(ValueError) as exc:
        schema.score_rows(name, frame)
    assert name in str(exc.value)
    for column in columns[:2]:
        assert column in str(exc.value)


@pytest.mark.parametrize('missing', [None, float('nan'), pd.NA, pd.NaT, '', ' \t '])
def test_completeness_and_score(missing):
    frame = pd.DataFrame([
        {'customer_id': 'CUS001', 'full_name': missing, 'email': 'a@b.com', 'status': 'active'},
        {'customer_id': 'CUS002', 'full_name': 'An', 'email': 'b@c.com', 'status': 'active'},
    ], index=[7, 7])
    scored = schema.score_rows('customers', frame)
    assert scored.iloc[0].to_dict() == {
        'row_id': 'CUS001', 'score': 75,
        'errors': ['MISSING_REQUIRED'], 'missing_cols': ['full_name'],
    }
    assert scored.iloc[1]['score'] == 100
    assert scored.iloc[1]['errors'] == []
    assert 'score' not in frame.columns


@pytest.mark.parametrize('name', schema.REQUIRED)
def test_all_missing_and_empty_frames(name):
    columns = schema.REQUIRED[name]
    scored = schema.score_rows(name, pd.DataFrame([{column: None for column in columns}]))
    assert scored.iloc[0]['score'] == 0
    assert scored.iloc[0]['missing_cols'] == columns
    empty = schema.score_rows(name, pd.DataFrame(columns=columns))
    assert empty.empty
    assert list(empty.columns) == ['row_id', 'score', 'errors', 'missing_cols']


def test_zero_is_present_and_score_is_rounded():
    frame = pd.DataFrame([{
        'order_item_id': 'ITM001', 'order_id': 'ORD001', 'product_id': 'PRD001',
        'quantity': None, 'unit_price': 0, 'discount_amount': 0,
    }])
    scored = schema.score_rows('order_items', frame)
    assert scored.iloc[0]['score'] == 83
    assert scored.iloc[0]['missing_cols'] == ['quantity']
