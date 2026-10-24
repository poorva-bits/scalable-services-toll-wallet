from time import time
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


def deduct(wallet_id: int, amount: int, reference_id: str) -> dict:
    # Atomic deduct: the balance check and the update are ONE SQL statement (Challenge 1, BR1)
    try:
        with engine.begin() as conn:
            res = conn.execute(
                text(
                    "UPDATE wallets SET balance = balance - :a WHERE id = :id AND balance >= :a"),
                {"a": amount, "id": wallet_id},
            )
            if res.rowcount == 0:  # either no such wallet or not enough balance
                exists = conn.execute(text("SELECT 1 FROM wallets WHERE id = :id"), {
                                      "id": wallet_id}).first()
                if exists is None:
                    raise AppError(404, "WALLET_NOT_FOUND", "Wallet not found")
                raise AppError(409, "INSUFFICIENT_BALANCE",
                               "Wallet balance is too low for this deduction")
            bal = conn.execute(text("SELECT balance FROM wallets WHERE id = :id"), {
                               "id": wallet_id}).scalar_one()
            conn.execute(  # ledger row in the same transaction (BR2)
                text(
                    "INSERT INTO wallet_ledger (wallet_id, type, amount, balance_after, reference_id) "
                    "VALUES (:w, 'DEDUCT', :a, :b, :r)"
                ),
                {"w": wallet_id, "a": amount, "b": bal, "r": reference_id},
            )
            return {"wallet_id": wallet_id, "type": "DEDUCT", "amount": amount,
                    "balance_after": bal, "reference_id": reference_id, "replayed": False}
    except IntegrityError:
        # same reference again: rolled back, return original
        return _replay(wallet_id, "DEDUCT", reference_id)


def list_ledger(wallet_id: int) -> list:
    # All ledger entries of a wallet in order
    get_wallet(wallet_id)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, type, amount, balance_after, reference_id, created_at "
                "FROM wallet_ledger WHERE wallet_id = :w ORDER BY id"
            ),
            {"w": wallet_id},
        ).mappings().all()
    return [dict(r) for r in rows]

def deduct_naive(wallet_id: int, amount: int, reference_id: str) -> dict:
    # DEMO ONLY: broken read-check-write used to prove the race in Challenge 1; never call from other services
    with engine.begin() as conn:
        bal = conn.execute(text("SELECT balance FROM wallets WHERE id = :id"), {"id": wallet_id}).scalar()
        if bal is None:
            raise AppError(404, "WALLET_NOT_FOUND", "Wallet not found")
        if bal < amount:  # check happens in Python, separate from the write
            raise AppError(409, "INSUFFICIENT_BALANCE", "Wallet balance is too low for this deduction")
        time.sleep(0.05)  # widen the race window so the bug is reproducible
        conn.execute(text("UPDATE wallets SET balance = :nb WHERE id = :id"), {"nb": bal - amount, "id": wallet_id})
        conn.execute(
            text(
                "INSERT INTO wallet_ledger (wallet_id, type, amount, balance_after, reference_id) "
                "VALUES (:w, 'DEDUCT', :a, :b, :r)"
            ),
            {"w": wallet_id, "a": amount, "b": bal - amount, "r": reference_id},
        )
        return {"wallet_id": wallet_id, "type": "DEDUCT", "amount": amount,
                "balance_after": bal - amount, "reference_id": reference_id, "replayed": False}