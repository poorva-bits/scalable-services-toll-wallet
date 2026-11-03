#!/usr/bin/env bash
# Expose every Kubernetes service on the same localhost ports Docker Compose uses (stop Compose first),
# so scripts/e2e_test.py and the challenge scripts run unchanged against the cluster. Ctrl+C stops all.
trap 'kill 0' EXIT
for pair in wallet:8001 toll-transaction:8002 vehicle-registry:8003 notification:8004 mock-bank:8005; do
  kubectl -n toll-wallet port-forward "svc/${pair%%:*}" "${pair##*:}:${pair##*:}" >/dev/null &
done
echo "Forwarding 8001-8005 to the toll-wallet namespace. Ctrl+C to stop."
wait
