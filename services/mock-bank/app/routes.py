from fastapi import APIRouter
from pydantic import BaseModel, Field

from app import bank

router = APIRouter()


class CollectIn(BaseModel):
    amount: int = Field(gt=0)  # paise, must be positive
    reference_id: str = Field(min_length=1, max_length=64)  # caller's unique id, makes retries safe


class ModeIn(BaseModel):
    mode: str


@router.post("/api/v1/collect")
def collect(body: CollectIn):
    # POST /api/v1/collect: behaves according to MODE
    return bank.collect(body.amount, body.reference_id)


@router.get("/api/v1/collections")
def collections():
    # GET /api/v1/collections: everything collected so far (evidence that retries do not double-collect)
    return bank.list_collections()


@router.get("/admin/mode")
def get_mode():
    return bank.get_mode()


@router.put("/admin/mode")
def set_mode(body: ModeIn):
    # PUT /admin/mode {"mode": "ok|slow|fail|flaky"}
    return bank.set_mode(body.mode.lower())


@router.post("/admin/reset", status_code=204)
def reset():
    bank.reset()
