"""Challenge 2: idempotency of POST /api/v1/crossings (Toll Transaction service).

Needs the stack running (docker compose up --build). Creates its own wallet and vehicle. Run from the repo root:
    python evidence/challenge2/run_challenge2.py
"""
import json
import threading
import urllib.error
import urllib.request
import uuid

TOLL = "http://localhost:8002/api/v1/crossings"
WALLET = "http://localhost:8001/api/v1/wallets"
REGISTRY = "http://localhost:8003/api/v1/vehicles"


def call(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, object]:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def main() -> None:
    tag = uuid.uuid4().hex[:6]
    wallet_id = call("POST", WALLET, {"fleet_id": f"c2-fleet-{tag}"})[1]["id"]
    call("POST", f"{WALLET}/{wallet_id}/topup", {"amount": 100000, "reference_id": f"c2-top-{tag}"})
    vehicle = f"C2-TRUCK-{tag}"
    call("POST", REGISTRY, {"vehicle_id": vehicle, "fleet_id": f"c2-fleet-{tag}", "wallet_id": wallet_id})
    body = {"vehicle_id": vehicle, "gate_id": "GATE-7", "amount": 5000}
    print(f"setup: wallet {wallet_id} balance 100000, vehicle {vehicle}, toll 5000")

    print("\n=== 1. Same Idempotency-Key sent 3 times in a row ===")
    key = f"c2-seq-{tag}"
    for i in range(3):
        status, resp = call("POST", TOLL, body, {"Idempotency-Key": key, "X-Request-ID": f"{key}-try{i + 1}"})
        print(f"  call {i + 1}: HTTP {status} {json.dumps(resp)}")

    print("\n=== 2. Same key, different payload (amount 9999) ===")
    status, resp = call("POST", TOLL, {**body, "amount": 9999}, {"Idempotency-Key": key})
    print(f"  HTTP {status} {json.dumps(resp)}")

    print("\n=== 3. 20 identical requests with one new key fired at the same moment ===")
    key = f"c2-par-{tag}"
    barrier, results = threading.Barrier(20), []

    def fire(n: int) -> None:
        barrier.wait()
        results.append(call("POST", TOLL, body, {"Idempotency-Key": key, "X-Request-ID": f"{key}-{n}"}))

    threads = [threading.Thread(target=fire, args=(n,)) for n in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    print(f"  status codes: {sorted(r[0] for r in results)}")
    print(f"  distinct crossing ids returned: {sorted({r[1].get('id') for r in results})}")

    print("\n=== Result ===")
    balance = call("GET", f"{WALLET}/{wallet_id}")[1]["balance"]
    deducts = [e for e in call("GET", f"{WALLET}/{wallet_id}/ledger")[1] if e["type"] == "DEDUCT"]
    print(f"  wallet balance: {balance} (expected 100000 - 2 x 5000 = 90000)")
    print(f"  wallet DEDUCT ledger rows: {len(deducts)} (expected 2, one per key)")
    print(f"  vehicle: {vehicle}  (count its crossings in toll_db, expected 2)")


if __name__ == "__main__":
    main()
