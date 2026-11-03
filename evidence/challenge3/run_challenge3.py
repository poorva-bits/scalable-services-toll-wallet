"""Challenge 3A: resilience of the Wallet -> Mock Bank call (timeout, retry with backoff + jitter, clean failure).

Needs the stack running (docker compose up --build). Run from the repo root:
    python evidence/challenge3/run_challenge3.py [--stop-bank]
Each scenario sets the bank's MODE, tops up a wallet, and prints the status, time taken and the wallet balance.
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

WALLET = "http://localhost:8001/api/v1/wallets"
BANK = "http://localhost:8005"


def call(method: str, url: str, body: dict | None = None, rid: str | None = None) -> tuple[int, object]:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "X-Request-ID": rid or ""})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def set_mode(mode: str) -> None:
    call("PUT", f"{BANK}/admin/mode", {"mode": mode})


def topup(wallet_id: int, label: str, amount: int = 50000) -> None:
    rid = f"c3-{label}-{uuid.uuid4().hex[:6]}"
    start = time.monotonic()
    status, body = call("POST", f"{WALLET}/{wallet_id}/topup", {"amount": amount, "reference_id": rid}, rid)
    took = time.monotonic() - start
    balance = call("GET", f"{WALLET}/{wallet_id}")[1]["balance"]
    print(f"  request_id={rid}")
    print(f"  -> HTTP {status} in {took:.2f}s")
    print(f"  -> body {json.dumps(body)}")
    print(f"  -> wallet balance now {balance}")
    print(f"  (retry log: docker compose logs wallet | grep {rid})")


def main() -> None:
    wallet_id = call("POST", WALLET, {"fleet_id": f"c3-fleet-{uuid.uuid4().hex[:6]}"})[1]["id"]
    print(f"wallet {wallet_id} created, balance 0")
    call("POST", f"{BANK}/admin/reset")

    print("\n=== 1. MODE=ok: bank healthy, succeeds on the first attempt ===")
    set_mode("ok")
    topup(wallet_id, "ok")

    print("\n=== 2. MODE=flaky: first 2 attempts get 503, client retries with backoff + jitter and succeeds ===")
    set_mode("flaky")
    topup(wallet_id, "flaky")

    print("\n=== 3. MODE=slow: every attempt exceeds the 2s timeout, client gives up cleanly with 502 ===")
    set_mode("slow")
    topup(wallet_id, "slow")

    print("\n=== 4. MODE=fail: bank keeps returning 503, client gives up cleanly with 502, balance unchanged ===")
    set_mode("fail")
    topup(wallet_id, "fail")

    print("\n=== Bank collections: each successful reference collected exactly once despite retries ===")
    for c in call("GET", f"{BANK}/api/v1/collections")[1]:
        print(f"  {c['reference_id']} amount={c['amount']} txn={c['transaction_id']}")

    if "--stop-bank" in sys.argv:
        print("\n=== 5. Bank container stopped: connection refused on every attempt, clean 502 ===")
        subprocess.run(["docker", "compose", "stop", "mock-bank"], check=True, capture_output=True)
        try:
            topup(wallet_id, "down")
        finally:
            subprocess.run(["docker", "compose", "start", "mock-bank"], check=True, capture_output=True)
            time.sleep(3)
    set_mode("ok")



if __name__ == "__main__":
    main()
