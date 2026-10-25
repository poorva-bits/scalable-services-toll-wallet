# Challenge 1: Concurrency (Wallet Service)

| Claim | Proof |
|---|---|
| The naive read-check-write breaks under parallel load | naive_run1.txt, screenshot_naive.png |
| The atomic conditional UPDATE allows exactly N deductions | safe_run1.txt, safe_run2.txt, safe_run3.txt, screenshot_safe.png |
| Balance never goes negative; one ledger row per success | "final balance" and "ledger DEDUCT rows" lines in the safe runs |

Run: start wallet on :8001, then `python run_test.py deduct` or `python run_test.py deduct-naive`.

## Limits
- Single MySQL instance; not tested across replicas or regions.
- Test uses one wallet; many wallets in parallel only touch separate rows.
- Safety relies on InnoDB row locking; a different engine would need re-checking.