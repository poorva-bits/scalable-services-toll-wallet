import logging
import random
import time

import httpx

from app import config

logger = logging.getLogger("wallet")


class BankUnavailable(Exception):
    # The bank could not be reached or kept failing after every retry
    pass


def _backoff(attempt: int) -> float:
    # Exponential backoff with full jitter: random wait in [0, base * 2^(attempt-1)], capped
    ceiling = min(config.BANK_BACKOFF_MAX, config.BANK_BACKOFF_BASE * 2 ** (attempt - 1))
    return random.uniform(0, ceiling)


def _post(amount: int, reference_id: str, request_id: str | None) -> httpx.Response:
    # One attempt; the same reference_id on every retry lets the bank de-duplicate
    return httpx.post(f"{config.BANK_URL}/api/v1/collect",
                      json={"amount": amount, "reference_id": reference_id},
                      headers={"X-Request-ID": request_id or ""}, timeout=config.BANK_TIMEOUT)


def collect(amount: int, reference_id: str, request_id: str | None = None) -> bool:
    # Challenge 3A: timeout + retry with backoff and jitter; True on success, False after the last failure
    if not config.BANK_URL:  # STUB: no bank configured (unit tests / local dev)
        return True
    last_error = ""
    for attempt in range(1, config.BANK_MAX_ATTEMPTS + 1):
        start = time.monotonic()
        try:
            r = _post(amount, reference_id, request_id)
            if r.status_code == 200:
                logger.info("rid=%s bank collect ref=%s ok attempt=%d/%d replayed=%s", request_id, reference_id,
                            attempt, config.BANK_MAX_ATTEMPTS, r.json().get("replayed"))
                return True
            if r.status_code < 500 and r.status_code != 429:  # client errors will not get better by retrying
                logger.warning("rid=%s bank collect ref=%s rejected status=%d, not retrying", request_id, reference_id, r.status_code)
                return False
            last_error = f"status {r.status_code}"
        except httpx.TimeoutException:
            last_error = f"timeout after {time.monotonic() - start:.1f}s"
        except httpx.HTTPError as e:
            last_error = f"{type(e).__name__}: {e}"
        if attempt == config.BANK_MAX_ATTEMPTS:
            break
        wait = _backoff(attempt)
        logger.warning("rid=%s bank collect ref=%s attempt=%d/%d failed (%s); retrying in %.2fs", request_id,
                       reference_id, attempt, config.BANK_MAX_ATTEMPTS, last_error, wait)
        time.sleep(wait)
    logger.error("rid=%s bank collect ref=%s gave up after %d attempts (%s)", request_id, reference_id,
                 config.BANK_MAX_ATTEMPTS, last_error)
    return False
