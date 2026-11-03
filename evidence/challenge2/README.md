# Challenge 2: Idempotency (Toll Transaction Service)

`POST /api/v1/crossings` charges a toll, so repeating it must never charge twice. The client sends an `Idempotency-Key` header; the logic lives in `services/toll-transaction/app/idempotency.py`.

## How it works
1. Fingerprint = SHA-256 of the request body with sorted keys.
2. `INSERT` the key with status `IN_PROGRESS` into `idempotency_keys` (primary key on the key). Only one request can win this insert, even if many arrive at the same moment.
3. The winner runs the crossing and stores the HTTP status and response body, setting status `DONE`.
4. Every other request with that key:
   - different fingerprint: **422 IDEMPOTENCY_KEY_REUSED**
   - `DONE`: returns the stored status and body (logged as `idempotency replay`)
   - `IN_PROGRESS`: polls until the winner finishes (up to `IDEMPOTENCY_WAIT_SECONDS`), then returns the stored response
5. If the winner crashes, the key is deleted so the client can safely retry.

A second guard: the crossing id is the wallet `reference_id`, and the wallet has a unique key on it.

## Evidence
| Claim | Proof |
|---|---|
| Same key repeated returns the same result and charges once | `run_output.txt` section 1 (crossing id 1 every time) |
| Same key with a different payload is rejected | `run_output.txt` section 2 (HTTP 422) |
| 20 simultaneous identical requests create one crossing | `run_output.txt` section 3 (one distinct id) |
| Only one record per key in the database | `db_state.txt` (2 crossings for 2 keys, both keys DONE with the same fingerprint) |
| Replays are visible in logs | `toll_replay_logs.txt` (`idempotency replay ... (no new work done)`) |
| Wallet charged exactly twice | `run_output.txt` result: balance 90000, 2 DEDUCT rows |
| Unit tests | `evidence/tests/toll_idempotency_unit_tests.txt` |

Run: `docker compose up --build`, then `python evidence/challenge2/run_challenge2.py` from the repo root.

## Limits
- Keys are kept forever; a production system would expire them (for example after 24 hours).
- A waiting duplicate holds a worker thread while it polls (bounded by `IDEMPOTENCY_WAIT_SECONDS`).
