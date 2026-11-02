from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import service
from app.errors import AppError

try:
    from app.idempotency import run_idempotent  # built for Challenge 2
except ImportError:
    def run_idempotent(key, body, do_work):
        # Fallback until idempotency.py is pushed
        return do_work()

router = APIRouter(prefix="/api/v1/crossings")


class CrossingIn(BaseModel):
    vehicle_id: str = Field(min_length=1, max_length=64)  # vehicle that crossed
    gate_id: str = Field(min_length=1, max_length=64)  # gate it crossed
    amount: int = Field(gt=0)  # toll in smallest currency unit, must be > 0


@router.post("")
def create_crossing(body: CrossingIn, request: Request, idempotency_key: str | None = Header(default=None)):
    # POST /api/v1/crossings: charge a toll once per Idempotency-Key
    if not idempotency_key:
        raise AppError(400, "IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key header is required")
    rid = request.state.request_id
    status, payload = run_idempotent(
        idempotency_key, body.model_dump(),
        lambda: service.create_crossing(body.vehicle_id, body.gate_id, body.amount, rid),
    )
    return JSONResponse(status_code=status, content=payload)


@router.get("/{crossing_id}")
def get_crossing(crossing_id: int):
    # GET /api/v1/crossings/{id}
    return service.get_crossing(crossing_id)