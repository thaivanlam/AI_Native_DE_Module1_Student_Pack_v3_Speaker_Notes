import pandas as pd
import pytest

from src.validators import business_validator as business


@pytest.mark.parametrize('email', ['bad', 'a@@b.com', 'a@b', 'a b@c.com', 'a@b.c\nextra'])
def test_invalid_email(email):
    valid, rejected = business.split_valid_invalid('customers', pd.DataFrame({'email': [email]}))
    assert valid.empty
    assert rejected['error_code'].tolist() == ['INVALID_EMAIL']


@pytest.mark.parametrize('name,column,allowed', [
    (name, column, allowed)
    for name, rules in business.ENUM_RULES.items()
    for column, allowed in rules.items()
])
def test_enum_membership(name, column, allowed):
    frame = pd.DataFrame({column: allowed + ['unknown']})
    valid, rejected = business.split_valid_invalid(name, frame)
    assert valid[column].tolist() == allowed
    assert rejected['error_code'].tolist() == [f'INVALID_{column.upper()}']


@pytest.mark.parametrize('name,column,code,kind', [
    (name, column, code, kind)
    for name, rules in business.RANGE_RULES.items()
    for column, code, kind in rules
])
def test_range_boundaries(name, column, code, kind):
    frame = pd.DataFrame({column: [-1, 0, 1, '2']})
    valid, rejected = business.split_valid_invalid(name, frame)
    assert len(rejected) == (2 if kind == 'pos' else 1)
    assert rejected['error_code'].tolist() == [code] * len(rejected)
    assert len(valid) + len(rejected) == len(frame)


def test_discount_boundary_and_multiple_errors():
    frame = pd.DataFrame({
        'quantity': [2, 2, 0], 'unit_price': [10, 10, -1],
        'discount_amount': [20, 21, 1],
    }, index=[7, 7, 2])
    original = frame.copy(deep=True)
    valid, rejected = business.split_valid_invalid('order_items', frame)
    assert valid.index.tolist() == [7]
    assert rejected.index.tolist() == [7, 2]
    assert rejected['error_code'].tolist() == [
        'DISCOUNT_EXCEEDS_GROSS',
        'NEGATIVE_PRICE|INVALID_QUANTITY|DISCOUNT_EXCEEDS_GROSS',
    ]
    assert business.count_violations(rejected) == {
        'DISCOUNT_EXCEEDS_GROSS': 2, 'NEGATIVE_PRICE': 1, 'INVALID_QUANTITY': 1,
    }
    pd.testing.assert_frame_equal(frame, original)
    assert 'error_code' not in valid.columns


def test_email_and_status_errors_are_joined():
    frame = pd.DataFrame({'email': ['bad', 'a@b.com'], 'status': ['unknown', 'active']})
    valid, rejected = business.split_valid_invalid('customers', frame)
    assert len(valid) == 1
    assert rejected['error_code'].tolist() == ['INVALID_EMAIL|INVALID_STATUS']


@pytest.mark.parametrize('name', ['customers', 'products', 'orders', 'order_items', 'payments'])
def test_empty_input(name):
    frame = pd.DataFrame()
    valid, rejected = business.split_valid_invalid(name, frame)
    assert valid.empty and rejected.empty
    assert list(rejected.columns) == ['error_code']
    assert business.count_violations(rejected) == {}


def test_missing_values_are_handled_by_schema_layer():
    frame = pd.DataFrame({'email': [None, pd.NA, ''], 'status': [None, pd.NA, ' ']})
    valid, rejected = business.split_valid_invalid('customers', frame)
    assert len(valid) == 3
    assert rejected.empty


@pytest.mark.parametrize('name', business.schema_validator.REQUIRED)
def test_dirty_dataset_partition(name):
    frame = business.schema_validator.load_dataset(name)
    valid, rejected = business.split_valid_invalid(name, frame)
    assert len(frame) == len(valid) + len(rejected)
    assert set(valid.index).isdisjoint(rejected.index)
    assert set(valid.index) | set(rejected.index) == set(frame.index)
    assert rejected['error_code'].str.len().gt(0).all()
