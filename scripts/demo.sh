#!/usr/bin/env bash
# Walk through the main workflow against a running stack (docker compose up --build -d --wait).
# Usage from the repo root: ./scripts/demo.sh      (macOS / Linux; needs curl and python3)
set -euo pipefail
W=http://localhost:8001/api/v1/wallets; T=http://localhost:8002/api/v1/crossings
R=http://localhost:8003/api/v1/vehicles; N=http://localhost:8004/api/v1/notifications
TAG=$(date +%s); FLEET="demo-fleet-$TAG"; TRUCK="DEMO-TRUCK-$TAG"; KEY="demo-key-$TAG"
pretty() { python3 -m json.tool; }
post() { curl -s -X POST "$1" -H 'Content-Type: application/json' "${@:3}" -d "$2"; }
step() { printf '\n\033[1m%s\033[0m\n' "$1"; }

step "1. Create a wallet for fleet $FLEET"
WALLET=$(post $W "{\"fleet_id\":\"$FLEET\"}" | tee /dev/stderr | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])"); echo

step "2. Top up 20000 paise (Wallet collects it from the Mock Bank first)"
post $W/$WALLET/topup '{"amount":20000,"reference_id":"demo-top-'$TAG'"}' | pretty

step "3. Register vehicle $TRUCK for wallet $WALLET in the Vehicle Registry"
post $R "{\"vehicle_id\":\"$TRUCK\",\"fleet_id\":\"$FLEET\",\"wallet_id\":$WALLET}" | pretty

step "4. The truck crosses a toll gate: 5000 paise (Toll -> Registry -> Wallet -> Notification)"
post $T "{\"vehicle_id\":\"$TRUCK\",\"gate_id\":\"G1\",\"amount\":5000}" -H "Idempotency-Key: $KEY" -H "X-Request-ID: demo-$TAG" | pretty

step "5. The gate retries the same request with the same Idempotency-Key (no second charge)"
post $T "{\"vehicle_id\":\"$TRUCK\",\"gate_id\":\"G1\",\"amount\":5000}" -H "Idempotency-Key: $KEY" | pretty

step "6. Balance: expect 15000"
curl -s $W/$WALLET | pretty

step "7. A toll larger than the balance: 409 INSUFFICIENT_BALANCE, crossing stored as FAILED"
post $T "{\"vehicle_id\":\"$TRUCK\",\"gate_id\":\"G1\",\"amount\":90000}" -H "Idempotency-Key: $KEY-big" | pretty

step "8. Notifications for wallet $WALLET: one TOLL_CHARGED and one LOW_BALANCE"
curl -s "$N?wallet_id=$WALLET" | python3 -c "import json,sys; [print(' ', n['type'], '-', n['message']) for n in json.load(sys.stdin)]"

step "9. The same request id in every service's logs"
docker compose logs --no-color toll-transaction vehicle-registry wallet notification 2>/dev/null | grep "demo-$TAG" | grep -v "INFO:  " || true
