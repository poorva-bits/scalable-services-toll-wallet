from sqlalchemy import text

from app import clients, state_machine
from app.db import engine
from app.errors import AppError


def _to_dict(row) -> dict:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(row).items()}


def get_crossing(crossing_id: int) -> dict:
    # Fetch one crossing or raise 404
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM crossings WHERE id = :id"), {"id": crossing_id}).mappings().first()
    if row is None:
        raise AppError(404, "CROSSING_NOT_FOUND", "Crossing not found")
    return _to_dict(row)


def _create_pending(vehicle_id: str, gate_id: str, amount: int) -> int:
    # Record the crossing as PENDING plus its first history row
    with engine.begin() as conn:
        res = conn.execute(
            text("INSERT INTO crossings (vehicle_id, gate_id, amount, status) VALUES (:v, :g, :a, 'PENDING')"),
            {"v": vehicle_id, "g": gate_id, "a": amount},
        )
        crossing_id = res.lastrowid
        conn.execute(text("INSERT INTO crossing_status_history (crossing_id, status) VALUES (:c, 'PENDING')"), {"c": crossing_id})
    return crossing_id


def _fail(crossing_id: int, http_status: int, code: str, message: str, request_id: str | None) -> tuple[int, dict]:
    # Mark the crossing FAILED and return an error body that also carries the crossing id
    state_machine.transition(crossing_id, "FAILED", reason=code)
    body = {"error": {"code": code, "message": message, "request_id": request_id},
            "crossing_id": crossing_id, "status": "FAILED"}
    return http_status, body


def create_crossing(vehicle_id: str, gate_id: str, amount: int, request_id: str | None) -> tuple[int, dict]:
    # Main flow: validate vehicle -> deduct from wallet -> notify -> complete; returns (http status, body)
    crossing_id = _create_pending(vehicle_id, gate_id, amount)
    try:
        vehicle = clients.get_vehicle(vehicle_id, request_id)
    except clients.DependencyError:
        return _fail(crossing_id, 502, "REGISTRY_UNAVAILABLE", "Vehicle registry is unavailable", request_id)
    if vehicle is None:
        return _fail(crossing_id, 404, "VEHICLE_NOT_FOUND", "Vehicle is not registered", request_id)
    if not vehicle.get("active"):
        return _fail(crossing_id, 409, "VEHICLE_INACTIVE", "Vehicle is not active", request_id)

    wallet_id = vehicle["wallet_id"]
    with engine.begin() as conn:  # remember which wallet this crossing is charged to
        conn.execute(text("UPDATE crossings SET wallet_id = :w WHERE id = :id"), {"w": wallet_id, "id": crossing_id})

    try:  # crossing id is the wallet reference_id, so the wallet also blocks double charging
        status, _ = clients.deduct(wallet_id, amount, f"crossing-{crossing_id}", request_id)
    except clients.DependencyError:
        return _fail(crossing_id, 502, "WALLET_UNAVAILABLE", "Wallet service is unavailable", request_id)
    if status == 409:
        return _fail(crossing_id, 409, "INSUFFICIENT_BALANCE", "Wallet balance is too low for this toll", request_id)
    if status == 404:
        return _fail(crossing_id, 404, "WALLET_NOT_FOUND", "Wallet for this vehicle was not found", request_id)
    if status != 200:
        return _fail(crossing_id, 502, "WALLET_ERROR", f"Wallet returned {status}", request_id)

    state_machine.transition(crossing_id, "CHARGED")
    clients.notify(wallet_id, "TOLL_CHARGED", f"Toll of {amount} charged for {vehicle_id}", request_id)
    state_machine.transition(crossing_id, "COMPLETED")
    return 201, get_crossing(crossing_id)