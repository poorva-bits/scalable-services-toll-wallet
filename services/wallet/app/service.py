from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import bank_client
from app.db import engine
from app.errors import AppError


def create_wallet(fleet_id: str) -> dict:
    # Insert a new empty wallet; one wallet per fleet
    try:
        with engine.begin() as conn:
            res = conn.execute(text("INSERT INTO wallets (fleet_id) VALUES (:f)"), {"f": fleet_id})
            return {"id": res.lastrowid, "fleet_id": fleet_id, "balance": 0}
    except IntegrityError:
        raise AppError(409, "WALLET_EXISTS", "A wallet already exists for this fleet")


def get_wallet(wallet_id: int) -> dict:
    # Fetch a wallet or raise 404
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, fleet_id, balance FROM wallets WHERE id = :id"), {"id": wallet_id}
        ).mappings().first()
    if row is None:
        raise AppError(404, "WALLET_NOT_FOUND", "Wallet not found")
    return dict(row)