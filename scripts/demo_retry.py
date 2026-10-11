"""Demo bounded retry + exponential backoff của src/api_client.py (Bài 2).

Chạy: python scripts/demo_retry.py > docs/evidence/06-retry-log.txt 2>&1
Script tự dừng rồi bật lại container mock-api bằng docker compose.
"""
import dataclasses
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import api_client
from src.api_client import MASK, fetch_all_pages, fetch_page
from src.config import SETTINGS

failures = []


def say(text: str = "") -> None:
    print(text, flush=True)


def check(label: str, ok: bool) -> None:
    say(f"[{'OK' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def compose(action: str) -> None:
    say(f"$ docker compose {action} mock-api")
    subprocess.run(
        ["docker", "compose", action, "mock-api"],
        cwd=SETTINGS.root, check=True, capture_output=True,
    )


def wait_until_healthy(seconds: int = 30) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if requests.get(SETTINGS.api_url + "/health", timeout=2).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return False


def timed_call(func, *args, **kwargs):
    """Trả về (kết quả | None, exception | None, số giây đã chạy)."""
    start = time.monotonic()
    try:
        return func(*args, **kwargs), None, time.monotonic() - start
    except RuntimeError as exc:
        return None, exc, time.monotonic() - start


def main() -> int:
    say("# 06-retry-log — Minh chung bounded retry + exponential backoff (Bai 2)")
    say(f"# Ngay chay: {datetime.now():%Y-%m-%d %H:%M:%S}")
    say(f"# Base URL: {SETTINGS.api_url} | X-API-Key: {MASK} | timeout=10 max_retries=3 backoff_seconds=1")

    say("\n== 1. Mock API dang chay -> goi thanh cong, khong retry")
    check("mock API healthy truoc khi demo", wait_until_healthy())
    payload, error, elapsed = timed_call(fetch_page, "orders", page=1, page_size=10)
    say(f"fetch_page('orders', page=1, page_size=10) -> rows={len(payload['data'])} "
        f"total={payload['total']} has_next={str(payload['has_next']).lower()} | {elapsed:.1f}s")
    check("lay duoc 10 dong ngay lan goi dau", error is None and len(payload["data"]) == 10)

    say("\n== 2. Dung mock API -> 3 lan thu, cho 1s, 2s, 4s -> RuntimeError")
    compose("stop")
    payload, error, elapsed = timed_call(fetch_page, "orders", page=1, page_size=10)
    say(f"-> {type(error).__name__}: {error}")
    say(f"-> nguyen nhan goc (__cause__): {type(error.__cause__).__name__}")
    say(f"-> tong thoi gian: {elapsed:.1f}s (backoff 1 + 2 + 4 = 7s, cong thoi gian ket noi that bai)")
    check(
        "nem RuntimeError dung thong diep sau 3 lan thu",
        str(error) == "API failed after 3 attempts: orders page 1",
    )
    check("giu exception goc qua 'from exc'", isinstance(error.__cause__, requests.RequestException))
    check("tong thoi gian cho >= 7s", elapsed >= 7)

    say("\n== 3. Bat lai mock API -> goi thanh cong")
    compose("start")
    check("mock API healthy sau khi bat lai", wait_until_healthy())
    rows, error, elapsed = timed_call(fetch_all_pages, "orders")
    say(f"fetch_all_pages('orders') -> rows={len(rows)} | {elapsed:.1f}s")
    check("lay du 600 orders sau khi API hoat dong lai", error is None and len(rows) == 600)

    say("\n== 4. Key sai (401) -> bao loi ngay, khong retry")
    api_client.SETTINGS = dataclasses.replace(SETTINGS, api_key="invalid-demo-key")
    try:
        payload, error, elapsed = timed_call(fetch_page, "orders", page=1, page_size=10)
    finally:
        api_client.SETTINGS = SETTINGS
    say(f"-> {type(error).__name__}: {error} | {elapsed:.1f}s")
    check("401 khong bi retry (ket thuc duoi 1s)", error is not None and "status 401" in str(error) and elapsed < 1)

    say(f"\nchecks failed: {len(failures)}")
    say(f"\nexit code: {1 if failures else 0}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
