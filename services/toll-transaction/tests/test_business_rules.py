import uuid

import pytest
from fastapi.testclient import TestClient

from app import service, state_machine
from app.main import app

client = TestClient(app)


def new_pending() -> int:
    # Helper: a fresh PENDING crossing
    return service._create_pending("TRUCK-T", "GATE-T", 1000)


def post_crossing(vehicle_id: str):
    # Helper: call the endpoint with a unique idempotency key
    return client.post("/api/v1/crossings", json={"vehicle_id": vehicle_id, "gate_id": "GATE-T", "amount": 1000},
                       headers={"Idempotency-Key": f"k-{uuid.uuid4()}"})


def test_br4_valid_path_pending_charged_completed():
    # BR4: the normal path is allowed
    cid = new_pending()
    state_machine.transition(cid, "CHARGED")
    state_machine.transition(cid, "COMPLETED")
    assert service.get_crossing(cid)["status"] == "COMPLETED"


def test_br4_completed_crossing_cannot_change():
    # BR4: a COMPLETED crossing is final
    cid = new_pending()
    state_machine.transition(cid, "CHARGED")
    state_machine.transition(cid, "COMPLETED")
    with pytest.raises(state_machine.InvalidTransition):
        state_machine.transition(cid, "FAILED")


def test_br4_cannot_skip_charged():
    # BR4: PENDING cannot jump straight to COMPLETED
    with pytest.raises(state_machine.InvalidTransition):
        state_machine.transition(new_pending(), "COMPLETED")


def test_unknown_vehicle_fails_crossing():
    # Unknown vehicle gives 404 and the crossing is recorded as FAILED (needs USE_STUBS=true)
    r = post_crossing("UNKNOWN-1")
    assert r.status_code == 404 and r.json()["error"]["code"] == "VEHICLE_NOT_FOUND"
    assert client.get(f"/api/v1/crossings/{r.json()['crossing_id']}").json()["status"] == "FAILED"


def test_inactive_vehicle_is_rejected():
    # Inactive vehicle gives 409 (needs USE_STUBS=true)
    assert post_crossing("INACTIVE-1").status_code == 409


def test_missing_idempotency_key_is_rejected():
    # Header is mandatory on POST /crossings
    r = client.post("/api/v1/crossings", json={"vehicle_id": "T1", "gate_id": "G1", "amount": 1000})
    assert r.status_code == 400