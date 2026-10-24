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


@router.post("/{wallet_id}/deduct")
def deduct(wallet_id: int, body: MoneyIn):
    # POST /api/v1/wallets/{id}/deduct
    return service.deduct(wallet_id, body.amount, body.reference_id)


@router.get("/{wallet_id}/ledger")
def ledger(wallet_id: int):
    # GET /api/v1/wallets/{id}/ledger
    return service.list_ledger(wallet_id)


@router.post("/{wallet_id}/deduct-naive")
def deduct_naive(wallet_id: int, body: MoneyIn):
    # DEMO ONLY: unsafe version for the Challenge 1 before/after comparison
    return service.deduct_naive(wallet_id, body.amount, body.reference_id)
