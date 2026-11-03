# End-to-end test

`scripts/e2e_test.py` runs the main transaction (a toll crossing: Toll Transaction -> Vehicle Registry -> Wallet -> Notification) and four failure paths against the running Docker Compose stack, and exits with code 1 if any check fails.

| Section | What it checks |
|---|---|
| 0 | All five services answer /health |
| 1 | Wallet created, topped up through the Mock Bank, vehicle registered |
| 2 | Crossing returns 201 COMPLETED, wallet charged exactly once, ledger reference is crossing-<id> |
| 3 | Insufficient balance: 409, crossing recorded FAILED, balance unchanged |
| 4 | Deactivated vehicle (BR5): 409 VEHICLE_INACTIVE, balance unchanged |
| 5 | Unregistered vehicle: 404 VEHICLE_NOT_FOUND |
| 6 | Bank down during top-up: 502 BANK_UNAVAILABLE after retries, balance unchanged |

Result: `run_output.txt`, 18 of 18 checks passed.

Note: in this run the notification container was a local stand-in answering /health on port 8004, because services/notification is not yet runnable in Compose (no requirements.txt, listens on 8000). Notification is best effort in the toll flow, so the other checks do not depend on it.
