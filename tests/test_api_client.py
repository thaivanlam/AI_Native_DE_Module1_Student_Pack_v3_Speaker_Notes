import logging

import pytest
import requests

from src import api_client
from src.api_client import fetch_all_pages, fetch_page
from src.config import SETTINGS


class FakeResponse:
    def __init__(self, status_code=200, payload=None, bad_json=False):
        self.status_code = status_code
        self._payload = payload
        self._bad_json = bad_json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error", response=self)

    def json(self):
        if self._bad_json:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


def page_payload(rows, has_next=False, page=1, total=None):
    return {
        "page": page,
        "page_size": 100,
        "total": len(rows) if total is None else total,
        "has_next": has_next,
        "data": rows,
    }


@pytest.fixture
def api(monkeypatch):
    """Thay requests.get bằng hàng đợi kết quả và ghi lại các lần sleep."""

    class Api:
        outcomes = []
        calls = []
        sleeps = []

    def fake_get(url, **kwargs):
        Api.calls.append({"url": url, **kwargs})
        outcome = Api.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    Api.outcomes, Api.calls, Api.sleeps = [], [], []
    monkeypatch.setattr(api_client.requests, "get", fake_get)
    monkeypatch.setattr(api_client.time, "sleep", Api.sleeps.append)
    return Api


@pytest.fixture
def log_records():
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = Capture()
    api_client.log.addHandler(handler)
    yield records
    api_client.log.removeHandler(handler)


def test_fetch_page_sends_key_params_and_timeout(api):
    api.outcomes = [FakeResponse(payload=page_payload([{"order_id": "ORD1"}]))]

    payload = fetch_page("orders", page=2, page_size=50, updated_after="2026-07-01T12:00:00Z")

    assert payload["data"] == [{"order_id": "ORD1"}]
    call = api.calls[0]
    assert call["url"] == f"{SETTINGS.api_url}/orders"
    assert call["headers"] == {"X-API-Key": SETTINGS.api_key}
    assert call["params"] == {"page": 2, "page_size": 50, "updated_after": "2026-07-01T12:00:00Z"}
    assert call["timeout"] == 10
    assert api.sleeps == []


def test_fetch_page_maps_table_name_to_endpoint(api):
    api.outcomes = [FakeResponse(payload=page_payload([]))]

    fetch_page("order_items")

    assert api.calls[0]["url"] == f"{SETTINGS.api_url}/order-items"


def test_fetch_page_recovers_after_transient_errors(api, log_records):
    api.outcomes = [
        requests.ConnectionError("connection refused"),
        requests.Timeout("read timed out"),
        FakeResponse(payload=page_payload([{"order_id": "ORD1"}])),
    ]

    payload = fetch_page("orders")

    assert payload["total"] == 1
    assert len(api.calls) == 3
    assert api.sleeps == [1, 2]
    warnings = [r.getMessage() for r in log_records if r.levelno == logging.WARNING]
    assert len(warnings) == 2
    assert "attempt 1/3" in warnings[0] and "ConnectionError" in warnings[0]
    assert "attempt 2/3" in warnings[1] and "Timeout" in warnings[1]


def test_fetch_page_raises_after_max_retries_with_exponential_backoff(api):
    api.outcomes = [requests.ConnectionError("connection refused")] * 3

    with pytest.raises(RuntimeError, match="API failed after 3 attempts: orders page 4") as excinfo:
        fetch_page("orders", page=4)

    assert len(api.calls) == 3
    assert api.sleeps == [1, 2, 4]
    assert isinstance(excinfo.value.__cause__, requests.ConnectionError)


def test_fetch_page_backoff_scales_with_backoff_seconds(api):
    api.outcomes = [requests.ConnectionError("down")] * 3

    with pytest.raises(RuntimeError):
        fetch_page("orders", backoff_seconds=0.5)

    assert api.sleeps == [0.5, 1.0, 2.0]


def test_fetch_page_retries_server_error_and_invalid_json(api):
    api.outcomes = [
        FakeResponse(status_code=503),
        FakeResponse(bad_json=True),
        FakeResponse(payload=page_payload([])),
    ]

    assert fetch_page("orders")["data"] == []
    assert len(api.calls) == 3


@pytest.mark.parametrize("status", [400, 401, 404, 422])
def test_fetch_page_does_not_retry_client_errors(api, status):
    api.outcomes = [FakeResponse(status_code=status)]

    with pytest.raises(RuntimeError, match=f"status {status}: orders page 1") as excinfo:
        fetch_page("orders")

    assert len(api.calls) == 1
    assert api.sleeps == []
    assert isinstance(excinfo.value.__cause__, requests.HTTPError)


def test_fetch_page_retries_rate_limit(api):
    api.outcomes = [FakeResponse(status_code=429), FakeResponse(payload=page_payload([]))]

    fetch_page("orders")

    assert len(api.calls) == 2


def test_api_key_never_logged_or_raised(api, log_records):
    leaky = requests.ConnectionError(f"failed with header X-API-Key={SETTINGS.api_key}")
    api.outcomes = [leaky] * 3

    with pytest.raises(RuntimeError) as excinfo:
        fetch_page("orders")

    assert log_records
    for record in log_records:
        assert SETTINGS.api_key not in record.getMessage()
    assert SETTINGS.api_key not in str(excinfo.value)


def test_fetch_all_pages_stops_when_has_next_false(api):
    api.outcomes = [
        FakeResponse(payload=page_payload([{"id": 1}, {"id": 2}], has_next=True, total=3)),
        FakeResponse(payload=page_payload([{"id": 3}], has_next=False, page=2, total=3)),
    ]

    rows = fetch_all_pages("orders", updated_after="2026-07-01T12:00:00Z")

    assert rows == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert [c["params"]["page"] for c in api.calls] == [1, 2]
    assert all(c["params"]["page_size"] == 100 for c in api.calls)
    assert all(c["params"]["updated_after"] == "2026-07-01T12:00:00Z" for c in api.calls)


def test_fetch_all_pages_omits_updated_after_when_not_given(api):
    api.outcomes = [FakeResponse(payload=page_payload([{"id": 1}]))]

    fetch_all_pages("orders")

    assert "updated_after" not in api.calls[0]["params"]


def test_fetch_all_pages_returns_empty_list_for_empty_result(api):
    api.outcomes = [FakeResponse(payload=page_payload([]))]

    assert fetch_all_pages("orders", updated_after="2099-01-01T00:00:00Z") == []
    assert len(api.calls) == 1


def test_fetch_all_pages_logs_progress_per_page(api, log_records):
    api.outcomes = [
        FakeResponse(payload=page_payload([{"id": 1}, {"id": 2}], has_next=True, total=3)),
        FakeResponse(payload=page_payload([{"id": 3}], has_next=False, page=2, total=3)),
    ]

    fetch_all_pages("orders")

    messages = [r.getMessage() for r in log_records if r.levelno == logging.INFO]
    assert messages == [
        "Fetched resource=orders page=1 rows=2 total_so_far=2",
        "Fetched resource=orders page=2 rows=1 total_so_far=3",
    ]
    assert not [r for r in log_records if r.levelno >= logging.WARNING]


def test_fetch_all_pages_warns_when_rows_differ_from_api_total(api, log_records):
    api.outcomes = [FakeResponse(payload=page_payload([{"id": 1}], total=5))]

    rows = fetch_all_pages("orders")

    assert len(rows) == 1
    warnings = [r.getMessage() for r in log_records if r.levelno == logging.WARNING]
    assert warnings == ["Row count mismatch resource=orders fetched=1 api_total=5"]
