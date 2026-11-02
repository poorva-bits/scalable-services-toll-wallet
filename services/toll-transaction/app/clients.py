import logging

import httpx

from app import config

logger = logging.getLogger("toll")


class DependencyError(Exception):
    # A downstream service was unreachable or returned a server error
    pass


def _headers(request_id: str | None) -> dict:
    # Pass the correlation id on to the next service
    return {"X-Request-ID": request_id or ""}


def get_vehicle(vehicle_id: str, request_id: str | None) -> dict | None:
    # Look up a vehicle in the Registry; None means unknown vehicle
    if config.USE_STUBS:  # STUB: UNKNOWN-* is not found, INACTIVE-* is inactive, anything else is fine
        if vehicle_id.startswith("UNKNOWN"):
            return None
        return {"vehicle_id": vehicle_id, "fleet_id": "stub-fleet",
                "wallet_id": config.STUB_WALLET_ID, "active": not vehicle_id.startswith("INACTIVE")}
    try:
        r = httpx.get(f"{config.REGISTRY_URL}/api/v1/vehicles/{vehicle_id}", headers=_headers(request_id), timeout=config.HTTP_TIMEOUT)
    except httpx.HTTPError as e:
        raise DependencyError(f"registry unreachable: {e}") from e
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise DependencyError(f"registry returned {r.status_code}")
    return r.json()


def deduct(wallet_id: int, amount: int, reference_id: str, request_id: str | None) -> tuple[int, dict]:
    # Ask the Wallet to deduct; returns its status code and JSON body
    try:
        r = httpx.post(f"{config.WALLET_URL}/api/v1/wallets/{wallet_id}/deduct",
                       json={"amount": amount, "reference_id": reference_id},
                       headers=_headers(request_id), timeout=config.HTTP_TIMEOUT)
    except httpx.HTTPError as e:
        raise DependencyError(f"wallet unreachable: {e}") from e
    return r.status_code, r.json()


def notify(wallet_id: int, type_: str, message: str, request_id: str | None) -> None:
    # Best-effort notification: a failure is logged but never fails the crossing
    if config.USE_STUBS:  # STUB: just log until the real Notification service exists
        logger.info("rid=%s [stub notify] wallet=%s type=%s msg=%s", request_id, wallet_id, type_, message)
        return
    try:
        httpx.post(f"{config.NOTIFICATION_URL}/api/v1/notifications",
                   json={"wallet_id": wallet_id, "type": type_, "message": message},
                   headers=_headers(request_id), timeout=config.HTTP_TIMEOUT)
    except httpx.HTTPError as e:
        logger.warning("rid=%s notification failed: %s", request_id, e)