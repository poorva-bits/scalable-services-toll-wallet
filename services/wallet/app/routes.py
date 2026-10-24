from fastapi import APIRouter
from pydantic import BaseModel, Field

from app import service

router = APIRouter(prefix="/api/v1/wallets")


class WalletIn(BaseModel):
    # fleet that owns the wallet
    fleet_id: str = Field(min_length=1, max_length=64)


class MoneyIn(BaseModel):
    amount: int = Field(gt=0)  # paise, must be positive
    # caller's unique id for this operation
    reference_id: str = Field(min_length=1, max_length=64)


@router.post("", status_code=201)
def create_wallet(body: WalletIn):
    # POST /api/v1/wallets
    return service.create_wallet(body.fleet_id)


@router.get("/{wallet_id}")
def get_wallet(wallet_id: int):
    # GET /api/v1/wallets/{id}
    return service.get_wallet(wallet_id)


@router.post("/{wallet_id}/topup")
def topup(wallet_id: int, body: MoneyIn):
    # POST /api/v1/wallets/{id}/topup
    return service.topup(wallet_id, body.amount, body.reference_id)
