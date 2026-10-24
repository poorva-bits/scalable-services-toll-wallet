import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE = "http://localhost:8001/api/v1/wallets"
# deduct (safe) or deduct-naive (broken)
ENDPOINT = sys.argv[1] if len(sys.argv) > 1 else "deduct"
START_BALANCE = 100_000  # paise = Rs 1000
AMOUNT = 10_000          # paise = Rs 100 per toll
REQUESTS = 30
EXPECTED_OK = START_BALANCE // AMOUNT

# makes all requests fire at the same moment
barrier = threading.Barrier(REQUESTS)


def fire(wallet_id: int) -> int:
    # Wait for every thread, then send one deduct request and return its status code
    barrier.wait()
    r = httpx.post(f"{BASE}/{wallet_id}/{ENDPOINT}",
                   json={"amount": AMOUNT, "reference_id": f"toll-{uuid.uuid4()}"}, timeout=30)
    return r.status_code


def main():
    # Create a funded wallet, hit it with parallel deductions, then verify the invariants
    wid = httpx.post(
        BASE, json={"fleet_id": f"c1-{uuid.uuid4()}"}).json()["id"]
    httpx.post(f"{BASE}/{wid}/topup", json={"amount": START_BALANCE,
               "reference_id": f"top-{uuid.uuid4()}"})
    with ThreadPoolExecutor(max_workers=REQUESTS) as pool:
        codes = list(pool.map(fire, [wid] * REQUESTS))
    balance = httpx.get(f"{BASE}/{wid}").json()["balance"]
    ledger = httpx.get(f"{BASE}/{wid}/ledger").json()
    deducts = [e for e in ledger if e["type"] == "DEDUCT"]
    ok, rejected = codes.count(200), codes.count(409)
    print(f"endpoint            : {ENDPOINT}")
    print(
        f"requests            : {REQUESTS} x {AMOUNT} paise against {START_BALANCE} paise")
    print(f"success (200)       : {ok}   (expected {EXPECTED_OK})")
    print(
        f"rejected (409)      : {rejected}   (expected {REQUESTS - EXPECTED_OK})")
    print(f"other status codes  : {REQUESTS - ok - rejected}")
    print(
        f"final balance       : {balance}   (expected {START_BALANCE - ok * AMOUNT} for {ok} successes)")
    print(f"ledger DEDUCT rows  : {len(deducts)}   (expected {ok})")
    passed = ok == EXPECTED_OK and balance == START_BALANCE - \
        ok * AMOUNT and len(deducts) == ok and balance >= 0
    print("RESULT              :",
          "PASS" if passed else "FAIL (race condition detected)")


if __name__ == "__main__":
    main()
