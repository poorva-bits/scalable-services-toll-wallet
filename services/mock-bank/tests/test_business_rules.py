import uuid

import pytest
from fastapi.testclient import TestClient

from app import bank, config
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_bank():
    # Every test starts in ok mode with no collections
    bank.reset()
    bank.set_mode("ok")
    yield
    bank.set_mode("ok")


def collect(ref: str, amount: int = 1000):
    return client.post("/api/v1/collect", json={"amount": amount, "reference_id": ref})


def test_ok_mode_collects():
    r = collect("r-ok")
    assert r.status_code == 200 and r.json()["status"] == "COLLECTED"


def test_brb1_same_reference_is_collected_once():
    # BR-B1: retrying a reference never collects twice
    first, second = collect("r-dup"), collect("r-dup")
    assert second.json()["replayed"] is True
    assert second.json()["transaction_id"] == first.json()["transaction_id"]
    assert len(client.get("/api/v1/collections").json()) == 1


def test_brb1_same_reference_different_amount_conflicts():
    collect("r-amt", 1000)
    r = collect("r-amt", 2000)
    assert r.status_code == 409 and r.json()["error"]["code"] == "REFERENCE_CONFLICT"


def test_fail_mode_returns_503_and_collects_nothing():
    client.put("/admin/mode", json={"mode": "fail"})
    r = collect("r-fail")
    assert r.status_code == 503 and r.json()["error"]["code"] == "BANK_DOWN"
    assert client.get("/api/v1/collections").json() == []


def test_flaky_mode_fails_first_attempts_then_succeeds():
    client.put("/admin/mode", json={"mode": "flaky"})
    ref = f"r-{uuid.uuid4()}"
    codes = [collect(ref).status_code for _ in range(config.FLAKY_FAILURES + 1)]
    assert codes == [503] * config.FLAKY_FAILURES + [200]


def test_slow_mode_delays(monkeypatch):
    monkeypatch.setattr(config, "SLOW_SECONDS", 0.2)
    client.put("/admin/mode", json={"mode": "slow"})
    import time
    t = time.monotonic()
    assert collect("r-slow").status_code == 200
    assert time.monotonic() - t >= 0.2


def test_invalid_mode_rejected():
    r = client.put("/admin/mode", json={"mode": "broken"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_MODE"
