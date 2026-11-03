from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import engine
from app.errors import AppError

COLUMNS = "vehicle_id, fleet_id, wallet_id, active"


def _to_dict(row) -> dict:
    return {**dict(row), "active": bool(row["active"])}


def register(vehicle_id: str, fleet_id: str, wallet_id: int) -> dict:
    # Register a new vehicle as active; a vehicle_id can only be registered once
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO vehicles (vehicle_id, fleet_id, wallet_id, active) VALUES (:v, :f, :w, TRUE)"),
                {"v": vehicle_id, "f": fleet_id, "w": wallet_id},
            )
    except IntegrityError:
        raise AppError(409, "VEHICLE_EXISTS", "This vehicle is already registered")
    return {"vehicle_id": vehicle_id, "fleet_id": fleet_id, "wallet_id": wallet_id, "active": True}


def get_vehicle(vehicle_id: str) -> dict:
    # Fetch a vehicle or raise 404
    with engine.connect() as conn:
        row = conn.execute(text(f"SELECT {COLUMNS} FROM vehicles WHERE vehicle_id = :v"), {"v": vehicle_id}).mappings().first()
    if row is None:
        raise AppError(404, "VEHICLE_NOT_FOUND", "Vehicle is not registered")
    return _to_dict(row)


def list_vehicles(fleet_id: str | None) -> list:
    # All vehicles, optionally only one fleet's
    sql = f"SELECT {COLUMNS} FROM vehicles" + (" WHERE fleet_id = :f" if fleet_id else "") + " ORDER BY vehicle_id"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"f": fleet_id}).mappings().all()
    return [_to_dict(r) for r in rows]


def set_active(vehicle_id: str, active: bool) -> dict:
    # Activate or deactivate a registered vehicle
    with engine.begin() as conn:
        res = conn.execute(text("UPDATE vehicles SET active = :a WHERE vehicle_id = :v"), {"a": active, "v": vehicle_id})
    if res.rowcount == 0:
        get_vehicle(vehicle_id)  # raises 404 if missing; otherwise the value was already set
    return get_vehicle(vehicle_id)


def assert_chargeable(vehicle_id: str) -> dict:
    # BR5: only a registered, active vehicle can be charged a toll
    vehicle = get_vehicle(vehicle_id)  # 404 VEHICLE_NOT_FOUND if not registered
    if not vehicle["active"]:
        raise AppError(409, "VEHICLE_INACTIVE", "Vehicle is not active")
    return {**vehicle, "chargeable": True}
