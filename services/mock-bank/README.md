# Mock Bank

Stands in for the fleet's bank when a wallet is topped up. It is our own mock (no real payments) and can be made slow or failing on demand, which is what Challenge 3 (resilience) needs. No database: state is kept in memory and cleared on restart.

## API
| Method | Path | Result |
|---|---|---|
| POST | `/api/v1/collect` body `{amount, reference_id}` | 200 `{transaction_id, reference_id, amount, status, replayed, attempt}`; 503 BANK_DOWN / BANK_FLAKY; 409 REFERENCE_CONFLICT; 422 |
| GET | `/api/v1/collections` | 200 list of collected references |
| GET / PUT | `/admin/mode` body `{mode}` | read or change the mode at runtime |
| POST | `/admin/reset` | 204, forget collections |
| GET | `/health` | 200 (includes current mode) |

## Modes (`MODE` env var or `PUT /admin/mode`)
| Mode | Behaviour |
|---|---|
| ok | collects immediately |
| slow | waits `SLOW_SECONDS` (default 5) before answering, longer than the wallet's timeout |
| fail | always 503 BANK_DOWN |
| flaky | first `FLAKY_FAILURES` (default 2) attempts for each reference_id get 503, then it succeeds |

## Business rule
| ID | Rule | Enforced in | Tests |
|---|---|---|---|
| BR7 | A reference_id is collected at most once, so caller retries never double-collect | `bank.collect` | `test_br7_*` |

## Run
```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --port 8005
```

## Test
`python -m pytest -v` (no database needed)
