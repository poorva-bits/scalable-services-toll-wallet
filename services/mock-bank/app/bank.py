import threading
import time
import uuid

from app import config
from app.errors import AppError

# In-memory state: this is a mock with no database; restarting the container clears it
_lock = threading.Lock()
_state = {"mode": config.MODE}
_collections: dict[str, dict] = {}  # reference_id -> collection
_attempts: dict[str, int] = {}  # reference_id -> attempts seen (for flaky mode)


def get_mode() -> dict:
    return {"mode": _state["mode"], "slow_seconds": config.SLOW_SECONDS, "flaky_failures": config.FLAKY_FAILURES}


def set_mode(mode: str) -> dict:
    # Switch behaviour on demand (used by the Challenge 3 script)
    if mode not in config.MODES:
        raise AppError(422, "INVALID_MODE", f"mode must be one of {', '.join(config.MODES)}")
    _state["mode"] = mode
    return get_mode()


def reset() -> None:
    # Forget all collections and attempt counters
    with _lock:
        _collections.clear()
        _attempts.clear()


def collect(amount: int, reference_id: str) -> dict:
    # Simulate collecting money from the fleet's bank account in the current mode
    mode = _state["mode"]
    with _lock:
        _attempts[reference_id] = _attempts.get(reference_id, 0) + 1
        attempt = _attempts[reference_id]
    if mode == "fail":
        raise AppError(503, "BANK_DOWN", "Bank is unavailable")
    if mode == "flaky" and attempt <= config.FLAKY_FAILURES:
        raise AppError(503, "BANK_FLAKY", f"Transient bank failure (attempt {attempt})")
    if mode == "slow":
        time.sleep(config.SLOW_SECONDS)
    with _lock:  # BR-B1: a reference_id is collected at most once; retries get the original result
        existing = _collections.get(reference_id)
        if existing is not None:
            if existing["amount"] != amount:
                raise AppError(409, "REFERENCE_CONFLICT", "reference_id was already used with a different amount")
            return {**existing, "replayed": True, "attempt": attempt}
        txn = {"transaction_id": str(uuid.uuid4()), "reference_id": reference_id, "amount": amount, "status": "COLLECTED"}
        _collections[reference_id] = txn
    return {**txn, "replayed": False, "attempt": attempt}


def list_collections() -> list:
    with _lock:
        return list(_collections.values())
