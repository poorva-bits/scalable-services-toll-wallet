from fastapi import APIRouter
from pydantic import BaseModel, Field

from app import service

router = APIRouter(prefix="/api/v1/wallets")


class WalletIn(BaseModel):
    fleet_id: str = Field(min_length=1, max_length=64)  # fleet that owns the wallet


class MoneyIn(BaseModel):
    amount: int = Field(gt=0)  # paise, must be positive
    reference_id: str = Field(min_length=1, max_length=64)  # caller's unique id for this operation


@router.post("", status_code=201)
def create_wallet(body: WalletIn):
    # POST /api/v1/wallets
    return service.create_wallet(body.fleet_id)


@router.get("/{wallet_id}")
def get_wallet(wallet_id: int):
    # GET /api/v1/wallets/{id}
    return service.get_wallet(wallet_id)