from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import bank_client
from app.db import engine
from app.errors import AppError


def create_wallet(fleet_id: str) -> dict:
    # Insert a new empty wallet; one wallet per fleet
    try:
        with engine.begin() as conn:
            res = conn.execute(
                text("INSERT INTO wallets (fleet_id) VALUES (:f)"), {"f": fleet_id})
            return {"id": res.lastrowid, "fleet_id": fleet_id, "balance": 0}
    except IntegrityError:
        raise AppError(409, "WALLET_EXISTS",
                       "A wallet already exists for this fleet")


def get_wallet(wallet_id: int) -> dict:
    # Fetch a wallet or raise 404
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, fleet_id, balance FROM wallets WHERE id = :id"), {
                "id": wallet_id}
        ).mappings().first()
    if row is None:
        raise AppError(404, "WALLET_NOT_FOUND", "Wallet not found")
    return dict(row)


def _replay(wallet_id: int, type_: str, reference_id: str) -> dict:
    # Return the original ledger entry when the same reference_id is posted again
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT type, amount, balance_after, reference_id FROM wallet_ledger "
                "WHERE wallet_id = :w AND type = :t AND reference_id = :r"
            ),
            {"w": wallet_id, "t": type_, "r": reference_id},
        ).mappings().first()
    if row is None:
        raise AppError(500, "INTERNAL_ERROR",
                       "Ledger entry missing for duplicate reference")
    return {**dict(row), "wallet_id": wallet_id, "replayed": True}


def topup(wallet_id: int, amount: int, reference_id: str) -> dict:
    # Credit the wallet once the bank confirms collection
    get_wallet(wallet_id)  # raises 404 if the wallet does not exist
    if not bank_client.collect(amount, reference_id):
        raise AppError(502, "BANK_UNAVAILABLE",
                       "Bank could not collect the amount")
    try:
        with engine.begin() as conn:  # balance update and ledger row commit together (BR2)
            conn.execute(text(
                "UPDATE wallets SET balance = balance + :a WHERE id = :id"), {"a": amount, "id": wallet_id})
            bal = conn.execute(text("SELECT balance FROM wallets WHERE id = :id"), {
                               "id": wallet_id}).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO wallet_ledger (wallet_id, type, amount, balance_after, reference_id) "
                    "VALUES (:w, 'TOPUP', :a, :b, :r)"
                ),
                {"w": wallet_id, "a": amount, "b": bal, "r": reference_id},
            )
            return {"wallet_id": wallet_id, "type": "TOPUP", "amount": amount,
                    "balance_after": bal, "reference_id": reference_id, "replayed": False}
    except IntegrityError:
        # duplicate reference: return the original result
        return _replay(wallet_id, "TOPUP", reference_id)
