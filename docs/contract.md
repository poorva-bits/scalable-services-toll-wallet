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