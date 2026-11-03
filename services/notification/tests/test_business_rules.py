import random

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)
BASE = "/api/v1/notifications"


def new_wallet() -> int:
    # Helper: a wallet id no other test uses
    return random.randint(10**6, 10**9)


def notify(wallet_id: int, type_: str, message: str = "msg"):
    return client.post(BASE, json={"wallet_id": wallet_id, "type": type_, "message": message})


def test_toll_charged_is_stored_and_listed():
    w = new_wallet()
    r = notify(w, "TOLL_CHARGED", "Toll of 5000 charged for TRUCK-1")
    assert r.status_code == 201 and r.json()["status"] == "SENT"
    listed = client.get(BASE, params={"wallet_id": w}).json()
    assert [n["type"] for n in listed] == ["TOLL_CHARGED"]


def test_br6_only_one_low_balance_until_recovery():
    # BR6: a second LOW_BALANCE for the same wallet is suppressed, not stored again
    w = new_wallet()
    first, second = notify(w, "LOW_BALANCE"), notify(w, "LOW_BALANCE")
    assert first.status_code == 201 and first.json()["suppressed"] is False
    assert second.status_code == 200 and second.json()["suppressed"] is True
    assert second.json()["id"] == first.json()["id"]
    assert len(client.get(BASE, params={"wallet_id": w, "type": "LOW_BALANCE"}).json()) == 1


def test_br6_low_balance_allowed_again_after_recovery():
    # BR6: a successful toll charge closes the alert, so the next low balance is reported again
    w = new_wallet()
    notify(w, "LOW_BALANCE")
    notify(w, "TOLL_CHARGED")
    again = notify(w, "LOW_BALANCE")
    assert again.status_code == 201 and again.json()["suppressed"] is False
    assert len(client.get(BASE, params={"wallet_id": w, "type": "LOW_BALANCE"}).json()) == 2


def test_br6_is_per_wallet():
    # One wallet's open alert does not suppress another wallet's
    a, b = new_wallet(), new_wallet()
    notify(a, "LOW_BALANCE")
    assert notify(b, "LOW_BALANCE").status_code == 201


def test_unknown_type_is_rejected():
    r = notify(new_wallet(), "SPAM")
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_notification_returns_404():
    r = client.get(f"{BASE}/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"
