"""End-to-end test of the main transaction (a toll crossing) and its failure paths, against the running stack.

Start everything with `docker compose up --build`, then run from the repo root:
    python scripts/e2e_test.py
Exits with code 1 if any check fails.
"""
import json
import sys
import urllib.error
import urllib.request
import uuid

WALLET = "http://localhost:8001/api/v1/wallets"
TOLL = "http://localhost:8002/api/v1/crossings"
REGISTRY = "http://localhost:8003/api/v1/vehicles"
BANK = "http://localhost:8005"
NOTIFY = "http://localhost:8004/api/v1/notifications"
HEALTH = {name: f"http://localhost:{port}/health" for name, port in
          [("wallet", 8001), ("toll-transaction", 8002), ("vehicle-registry", 8003), ("notification", 8004), ("mock-bank", 8005)]}

failures = 0


def call(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, object]:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def crossing(vehicle: str, amount: int, rid: str) -> tuple[int, dict]:
    return call("POST", TOLL, {"vehicle_id": vehicle, "gate_id": "GATE-E2E", "amount": amount},
                {"Idempotency-Key": f"e2e-{uuid.uuid4()}", "X-Request-ID": rid})


def balance(wallet_id: int) -> int:
    return call("GET", f"{WALLET}/{wallet_id}")[1]["balance"]


def main() -> None:
    tag = uuid.uuid4().hex[:6]
    print("=== 0. All services healthy ===")
    for name, url in HEALTH.items():
        status, _ = call("GET", url)
        check(f"{name} /health", status == 200, f"HTTP {status}")

    print("\n=== 1. Setup: wallet, top-up through the bank, vehicle ===")
    call("PUT", f"{BANK}/admin/mode", {"mode": "ok"})
    wallet_id = call("POST", WALLET, {"fleet_id": f"e2e-fleet-{tag}"})[1]["id"]
    status, _ = call("POST", f"{WALLET}/{wallet_id}/topup", {"amount": 20000, "reference_id": f"e2e-top-{tag}"})
    check("top-up of 20000 via Mock Bank", status == 200 and balance(wallet_id) == 20000, f"HTTP {status}")
    vehicle = f"E2E-TRUCK-{tag}"
    status, _ = call("POST", REGISTRY, {"vehicle_id": vehicle, "fleet_id": f"e2e-fleet-{tag}", "wallet_id": wallet_id})
    check("vehicle registered", status == 201, f"HTTP {status}")

    print("\n=== 2. Main transaction: crossing -> Registry -> Wallet -> Notification ===")
    status, body = crossing(vehicle, 5000, f"e2e-ok-{tag}")
    check("crossing returns 201 COMPLETED", status == 201 and body.get("status") == "COMPLETED", f"HTTP {status}")
    check("wallet charged once: balance 15000", balance(wallet_id) == 15000, f"balance {balance(wallet_id)}")
    ledger = call("GET", f"{WALLET}/{wallet_id}/ledger")[1]
    check("ledger DEDUCT uses reference crossing-<id>",
          any(e["type"] == "DEDUCT" and e["reference_id"] == f"crossing-{body.get('id')}" for e in ledger))
    charged = call("GET", f"{NOTIFY}?wallet_id={wallet_id}&type=TOLL_CHARGED")[1]
    check("Notification stored one TOLL_CHARGED for the wallet", len(charged) == 1, f"{len(charged)} stored")

    print("\n=== 3. Failure path: insufficient balance ===")
    status, body = crossing(vehicle, 50000, f"e2e-low-{tag}")
    check("409 INSUFFICIENT_BALANCE", status == 409 and body["error"]["code"] == "INSUFFICIENT_BALANCE", f"HTTP {status}")
    check("crossing recorded as FAILED", call("GET", f"{TOLL}/{body.get('crossing_id')}")[1].get("status") == "FAILED")
    check("balance unchanged at 15000", balance(wallet_id) == 15000)
    crossing(vehicle, 50000, f"e2e-low2-{tag}")
    low = call("GET", f"{NOTIFY}?wallet_id={wallet_id}&type=LOW_BALANCE")[1]
    check("two low-balance failures -> one LOW_BALANCE notification (BR6)", len(low) == 1, f"{len(low)} stored")

    print("\n=== 4. Failure path: deactivated vehicle (BR5) ===")
    call("PATCH", f"{REGISTRY}/{vehicle}", {"active": False})
    status, body = crossing(vehicle, 5000, f"e2e-inactive-{tag}")
    check("409 VEHICLE_INACTIVE", status == 409 and body["error"]["code"] == "VEHICLE_INACTIVE", f"HTTP {status}")
    check("balance unchanged at 15000", balance(wallet_id) == 15000)

    print("\n=== 5. Failure path: unregistered vehicle ===")
    status, body = crossing(f"NOPE-{tag}", 5000, f"e2e-unknown-{tag}")
    check("404 VEHICLE_NOT_FOUND", status == 404 and body["error"]["code"] == "VEHICLE_NOT_FOUND", f"HTTP {status}")

    print("\n=== 6. Failure path: bank down during top-up ===")
    call("PUT", f"{BANK}/admin/mode", {"mode": "fail"})
    try:
        status, body = call("POST", f"{WALLET}/{wallet_id}/topup", {"amount": 10000, "reference_id": f"e2e-top2-{tag}"})
    finally:
        call("PUT", f"{BANK}/admin/mode", {"mode": "ok"})
    check("502 BANK_UNAVAILABLE after retries", status == 502 and body["error"]["code"] == "BANK_UNAVAILABLE", f"HTTP {status}")
    check("balance unchanged at 15000", balance(wallet_id) == 15000)

    print(f"\nRESULT: {'PASS' if failures == 0 else 'FAIL'} ({failures} failed checks)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
