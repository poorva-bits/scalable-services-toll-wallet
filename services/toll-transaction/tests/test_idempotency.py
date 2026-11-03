import threading
import uuid

import pytest

from app import idempotency
from app.errors import AppError


def counting_work(calls: list):
    # Helper: fake crossing that records how many times it really ran
    def work():
        calls.append(1)
        return 201, {"id": len(calls), "status": "COMPLETED"}
    return work


def test_same_key_same_body_runs_once_and_replays():
    calls, key, body = [], f"k-{uuid.uuid4()}", {"vehicle_id": "T1", "gate_id": "G1", "amount": 100}
    first = idempotency.run_idempotent(key, body, counting_work(calls))
    second = idempotency.run_idempotent(key, body, counting_work(calls))
    assert first == second == (201, {"id": 1, "status": "COMPLETED"})
    assert len(calls) == 1


def test_same_key_different_body_is_rejected():
    key = f"k-{uuid.uuid4()}"
    idempotency.run_idempotent(key, {"amount": 100}, counting_work([]))
    with pytest.raises(AppError) as e:
        idempotency.run_idempotent(key, {"amount": 999}, counting_work([]))
    assert e.value.status == 422 and e.value.code == "IDEMPOTENCY_KEY_REUSED"


def test_fingerprint_ignores_key_order():
    assert idempotency.fingerprint({"a": 1, "b": 2}) == idempotency.fingerprint({"b": 2, "a": 1})


def test_simultaneous_identical_requests_do_work_once():
    calls, key, body, results = [], f"k-{uuid.uuid4()}", {"amount": 100}, []
    barrier = threading.Barrier(10)

    def slow_work():
        calls.append(1)
        threading.Event().wait(0.3)  # keep the key IN_PROGRESS while the others arrive
        return 201, {"id": 7}

    def call():
        barrier.wait()
        results.append(idempotency.run_idempotent(key, body, slow_work))

    threads = [threading.Thread(target=call) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(calls) == 1
    assert results == [(201, {"id": 7})] * 10


def test_crash_releases_key_for_retry():
    key, body = f"k-{uuid.uuid4()}", {"amount": 100}

    def boom():
        raise RuntimeError("db down")

    with pytest.raises(RuntimeError):
        idempotency.run_idempotent(key, body, boom)
    assert idempotency.run_idempotent(key, body, counting_work([]))[0] == 201
