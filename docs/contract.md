# Shared Contract (draft)

- Ports: wallet 8001, toll-transaction 8002, vehicle-registry 8003, notification 8004, mock-bank 8005
- Money: integer paise (never floats)
- Headers: `X-Request-ID` (passed on every call), `Idempotency-Key` (on state-changing calls)
- Error JSON: `{"error": {"code": "INSUFFICIENT_BALANCE", "message": "...", "request_id": "..."}}`
- Config: all URLs/credentials via env vars, nothing hard-coded to localhost

## Wallet API (base: /api/v1/wallets)
- POST   /                   body {fleet_id}                    -> 201 {id, fleet_id, balance}
- GET    /{id}                                                  -> 200 {id, fleet_id, balance}
- POST   /{id}/topup         body {amount, reference_id}        -> 200 ledger entry
- POST   /{id}/deduct        body {amount, reference_id}        -> 200 ledger entry | 409 INSUFFICIENT_BALANCE | 404 WALLET_NOT_FOUND
- GET    /{id}/ledger                                           -> 200 [ledger entries]
- Same reference_id posted twice returns the original entry with "replayed": true

## Toll Transaction API (base: /api/v1/crossings)
- POST /   headers Idempotency-Key (required), X-Request-ID; body {vehicle_id, gate_id, amount}
           -> 201 {id, vehicle_id, gate_id, wallet_id, amount, status: COMPLETED}
           -> 404 VEHICLE_NOT_FOUND | 409 VEHICLE_INACTIVE | 409 INSUFFICIENT_BALANCE | 502 REGISTRY_UNAVAILABLE / WALLET_UNAVAILABLE
           (failed crossings are still recorded: the error body carries crossing_id and status FAILED)
- GET /{id} -> 200 crossing | 404 CROSSING_NOT_FOUND

## Services Toll Transaction calls
- Vehicle Registry: GET /api/v1/vehicles/{vehicle_id} -> {vehicle_id, fleet_id, wallet_id, active} | 404
- Wallet: POST /api/v1/wallets/{id}/deduct {amount, reference_id = "crossing-<id>"}
- Notification: POST /api/v1/notifications {wallet_id, type, message} (best effort, never fails a crossing)