import time

import requests

from src.config import SETTINGS
from src.logger import get_logger

log = get_logger("api_client")

MASK = "******"
RETRYABLE_4XX = (408, 429)


def _describe(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}".replace(SETTINGS.api_key, MASK)


def _is_client_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if response is None:
        return False
    return 400 <= response.status_code < 500 and response.status_code not in RETRYABLE_4XX


def fetch_page(
    resource: str,
    page: int = 1,
    page_size: int = 100,
    updated_after: str | None = None,
    timeout: int = 10,
    max_retries: int = 3,
    backoff_seconds: float = 1,
) -> dict:
    url = f"{SETTINGS.api_url}/{resource.replace('_', '-')}"
    params = {"page": page, "page_size": page_size}
    if updated_after:
        params["updated_after"] = updated_after
    headers = {"X-API-Key": SETTINGS.api_key}

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            if _is_client_error(exc):
                # 4xx là lỗi tham số/xác thực: gọi lại vẫn nhận cùng kết quả nên không retry.
                log.error(
                    "API request rejected resource=%s page=%d | %s",
                    resource, page, _describe(exc),
                )
                raise RuntimeError(
                    f"API rejected request with status {exc.response.status_code}: "
                    f"{resource} page {page}"
                ) from exc

            wait = backoff_seconds * (2 ** (attempt - 1))
            log.warning(
                "API call failed attempt %d/%d resource=%s page=%d | %s | backoff=%ss",
                attempt, max_retries, resource, page, _describe(exc), wait,
            )
            time.sleep(wait)
            if attempt == max_retries:
                raise RuntimeError(
                    f"API failed after {max_retries} attempts: {resource} page {page}"
                ) from exc


def fetch_all_pages(
    resource: str,
    updated_after: str | None = None,
    page_size: int = 100,
    timeout: int = 10,
    max_retries: int = 3,
    backoff_seconds: float = 1,
) -> list:
    rows = []
    page = 1
    while True:
        payload = fetch_page(
            resource, page, page_size, updated_after, timeout, max_retries, backoff_seconds
        )
        page_rows = payload.get("data", [])
        rows.extend(page_rows)
        log.info(
            "Fetched resource=%s page=%d rows=%d total_so_far=%d",
            resource, page, len(page_rows), len(rows),
        )
        if not payload.get("has_next"):
            break
        page += 1

    total = payload.get("total")
    if total is not None and total != len(rows):
        log.warning(
            "Row count mismatch resource=%s fetched=%d api_total=%d",
            resource, len(rows), total,
        )
    return rows
