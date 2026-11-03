# Challenge 3A: Resilience (Wallet -> Mock Bank)

A wallet top-up first collects the money from the fleet's bank (`services/mock-bank`). The call is made by `services/wallet/app/bank_client.py`:

| Mechanism | Setting (env) | Default |
|---|---|---|
| Timeout per attempt | `BANK_TIMEOUT` | 2 s |
| Attempts (first try + retries) | `BANK_MAX_ATTEMPTS` | 4 |
| Exponential backoff with full jitter: wait = random(0, base x 2^(n-1)) | `BANK_BACKOFF_BASE`, `BANK_BACKOFF_MAX` | 0.5 s, cap 4 s |
| Retried on | timeouts, connection errors, 5xx, 429 | |
| Not retried on | other 4xx (retrying will not help) | |
| Clean failure | HTTP 502 `BANK_UNAVAILABLE`, wallet not credited | |

Retries are safe: every attempt sends the same `reference_id`, and the bank collects a reference at most once (BR7). Jitter keeps many clients from retrying in lockstep after an outage.

The mock bank's `MODE` (`ok`, `slow`, `fail`, `flaky`) is switched at runtime with `PUT /admin/mode`.

## Evidence
| Scenario | Result | Proof |
|---|---|---|
| ok | 200 on attempt 1 | `run_output.txt` section 1 |
| flaky (2 x 503 then ok) | 200 after 2 retries, 0.86 s | section 2, `wallet_retry_logs.txt` (`attempt=1/4 failed (status 503); retrying in 0.79s`...) |
| slow (5 s > 2 s timeout) | 4 timeouts, clean 502 in about 9.8 s | section 3 |
| fail (always 503) | clean 502 in under 1 s, balance unchanged | section 4 |
| bank container stopped | connection errors, clean 502 | section 5 |
| no double collection | each successful reference appears once in the bank | "Bank collections" in `run_output.txt` |

Run: `docker compose up --build`, then `python evidence/challenge3/run_challenge3.py --stop-bank` from the repo root.

## Finding: timeout does not mean "not done"
In slow mode the bank still finishes the collection after the wallet has given up, so the bank shows `c3-slow-...` as collected while the wallet was not credited. A timeout only means "unknown". Because the bank de-duplicates by `reference_id`, retrying the same top-up later credits the wallet without collecting twice. A production system would add a reconciliation job that checks the bank for references that timed out.
