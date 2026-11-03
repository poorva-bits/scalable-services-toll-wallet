import hashlib
import json
import logging
import time
from typing import Callable

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import config
from app.db import engine
from app.errors import AppError

logger = logging.getLogger("toll")


def fingerprint(body: dict) -> str:
    # Stable hash of the request body: same fields and values give the same hash regardless of key order
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _claim(key: str, request_hash: str) -> bool:
    # Try to become the one request that does the work; the primary key lets only one INSERT win
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO idempotency_keys (idem_key, request_hash) VALUES (:k, :h)"),
                         {"k": key, "h": request_hash})
        return True
    except IntegrityError:
        return False


def _load(key: str):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT request_hash, status, response_code, response_body FROM idempotency_keys WHERE idem_key = :k"),
            {"k": key},
        ).mappings().first()


def _wait_for_result(key: str, request_hash: str) -> tuple[int, dict]:
    # Another request owns this key: check the fingerprint, then wait for (or return) its stored response
    deadline = time.monotonic() + config.IDEMPOTENCY_WAIT_SECONDS
    while True:
        row = _load(key)
        if row is None:  # the owner failed and released the key; caller may retry
            raise AppError(409, "IDEMPOTENCY_RETRY", "Previous request with this key failed; retry")
        if row["request_hash"] != request_hash:
            raise AppError(422, "IDEMPOTENCY_KEY_REUSED", "Idempotency-Key was already used with a different request body")
        if row["status"] == "DONE":
            body = row["response_body"]
            return row["response_code"], json.loads(body) if isinstance(body, str) else body
        if time.monotonic() >= deadline:
            raise AppError(409, "REQUEST_IN_PROGRESS", "A request with this Idempotency-Key is still being processed")
        time.sleep(0.05)


def run_idempotent(key: str, body: dict, do_work: Callable[[], tuple[int, dict]]) -> tuple[int, dict]:
    # Challenge 2: run do_work at most once per key; repeats (even simultaneous ones) get the stored response
    request_hash = fingerprint(body)
    if not _claim(key, request_hash):
        status, payload = _wait_for_result(key, request_hash)
        logger.info("idempotency replay key=%s status=%s (no new work done)", key, status)
        return status, payload
    try:
        status, payload = do_work()
    except Exception:
        with engine.begin() as conn:  # unexpected crash: release the key so the client can safely retry
            conn.execute(text("DELETE FROM idempotency_keys WHERE idem_key = :k"), {"k": key})
        raise
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE idempotency_keys SET status = 'DONE', response_code = :c, response_body = :b WHERE idem_key = :k"),
            {"c": status, "b": json.dumps(payload), "k": key},
        )
    logger.info("idempotency stored key=%s status=%s", key, status)
    return status, payload
