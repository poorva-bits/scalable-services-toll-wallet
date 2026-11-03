from fastapi import APIRouter
from pydantic import BaseModel, Field

from app import service

router = APIRouter(prefix="/api/v1/vehicles")


class VehicleIn(BaseModel):
    vehicle_id: str = Field(min_length=1, max_length=64)  # e.g. number plate
    fleet_id: str = Field(min_length=1, max_length=64)  # fleet that owns the vehicle
    wallet_id: int = Field(gt=0)  # wallet the tolls are charged to (id only, owned by Wallet service)


class StatusIn(BaseModel):
    active: bool


@router.post("", status_code=201)
def register(body: VehicleIn):
    # POST /api/v1/vehicles
    return service.register(body.vehicle_id, body.fleet_id, body.wallet_id)


@router.get("")
def list_vehicles(fleet_id: str | None = None):
    # GET /api/v1/vehicles?fleet_id=...
    return service.list_vehicles(fleet_id)


@router.get("/{vehicle_id}")
def get_vehicle(vehicle_id: str):
    # GET /api/v1/vehicles/{vehicle_id}: used by Toll Transaction before charging
    return service.get_vehicle(vehicle_id)


@router.patch("/{vehicle_id}")
def set_status(vehicle_id: str, body: StatusIn):
    # PATCH /api/v1/vehicles/{vehicle_id}: activate or deactivate
    return service.set_active(vehicle_id, body.active)


@router.get("/{vehicle_id}/chargeable")
def chargeable(vehicle_id: str):
    # GET /api/v1/vehicles/{vehicle_id}/chargeable: BR5 check as an API
    return service.assert_chargeable(vehicle_id)
