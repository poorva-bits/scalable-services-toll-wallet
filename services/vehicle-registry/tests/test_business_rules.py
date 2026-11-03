import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "/api/v1/vehicles"


def new_vehicle(active: bool = True) -> str:
    # Helper: register a fresh vehicle and optionally deactivate it
    vid = f"TRUCK-{uuid.uuid4().hex[:8]}"
    client.post(BASE, json={"vehicle_id": vid, "fleet_id": "fleet-t", "wallet_id": 1})
    if not active:
        client.patch(f"{BASE}/{vid}", json={"active": False})
    return vid


def test_br3_registered_active_vehicle_is_chargeable():
    # BR3: a registered, active vehicle can be charged
    r = client.get(f"{BASE}/{new_vehicle()}/chargeable")
    assert r.status_code == 200 and r.json()["chargeable"] is True


def test_br3_inactive_vehicle_cannot_be_charged():
    # BR3: a deactivated vehicle is rejected with 409
    vid = new_vehicle(active=False)
    assert client.get(f"{BASE}/{vid}").json()["active"] is False
    r = client.get(f"{BASE}/{vid}/chargeable")
    assert r.status_code == 409 and r.json()["error"]["code"] == "VEHICLE_INACTIVE"


def test_br3_unregistered_vehicle_cannot_be_charged():
    # BR3: an unknown vehicle is rejected with 404
    r = client.get(f"{BASE}/NOPE-{uuid.uuid4().hex[:8]}/chargeable")
    assert r.status_code == 404 and r.json()["error"]["code"] == "VEHICLE_NOT_FOUND"


def test_get_returns_contract_fields():
    # GET returns exactly what Toll Transaction relies on
    vid = new_vehicle()
    assert client.get(f"{BASE}/{vid}").json() == {"vehicle_id": vid, "fleet_id": "fleet-t", "wallet_id": 1, "active": True}


def test_duplicate_registration_is_rejected():
    # The same vehicle cannot be registered twice
    vid = new_vehicle()
    r = client.post(BASE, json={"vehicle_id": vid, "fleet_id": "fleet-x", "wallet_id": 2})
    assert r.status_code == 409 and r.json()["error"]["code"] == "VEHICLE_EXISTS"


def test_invalid_wallet_id_is_rejected():
    # wallet_id must be a positive id
    r = client.post(BASE, json={"vehicle_id": "T-BAD", "fleet_id": "f", "wallet_id": 0})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
