import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "/api/v1/wallets"


def new_wallet(balance: int = 0) -> int:
    # Helper: create a fresh wallet (unique fleet) and optionally top it up
    wid = client.post(BASE, json={"fleet_id": f"fleet-{uuid.uuid4()}"}).json()["id"]
    if balance:
        client.post(f"{BASE}/{wid}/topup", json={"amount": balance, "reference_id": f"top-{uuid.uuid4()}"})
    return wid


def deduct(wid: int, amount: int, ref: str | None = None):
    # Helper: call deduct with a unique reference unless one is given
    return client.post(f"{BASE}/{wid}/deduct", json={"amount": amount, "reference_id": ref or f"d-{uuid.uuid4()}"})


def test_br1_balance_never_negative():
    # BR1: over-deduction is rejected and balance is unchanged
    wid = new_wallet(1000)
    r = deduct(wid, 2000)
    assert r.status_code == 409 and r.json()["error"]["code"] == "INSUFFICIENT_BALANCE"
    assert client.get(f"{BASE}/{wid}").json()["balance"] == 1000


def test_br2_one_ledger_entry_per_balance_change():
    # BR2: top-up + deduct produce exactly two ledger rows with correct balance_after
    wid = new_wallet(1000)
    deduct(wid, 300)
    ledger = client.get(f"{BASE}/{wid}/ledger").json()
    assert len(ledger) == 2 and ledger[-1]["balance_after"] == 700


def test_duplicate_reference_is_replayed_not_double_charged():
    # Same reference_id twice returns the original entry and charges once
    wid = new_wallet(1000)
    ref = f"d-{uuid.uuid4()}"
    deduct(wid, 300, ref)
    second = deduct(wid, 300, ref)
    assert second.status_code == 200 and second.json()["replayed"] is True
    assert client.get(f"{BASE}/{wid}").json()["balance"] == 700


def test_amount_must_be_positive():
    # Zero or negative amounts are rejected with 422
    wid = new_wallet(1000)
    assert deduct(wid, 0).status_code == 422


def test_unknown_wallet_returns_404():
    # Deducting from a wallet that does not exist gives 404
    assert deduct(999999999, 100).status_code == 404