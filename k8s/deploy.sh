#!/usr/bin/env bash
# Deploy the whole application to Minikube. Run from the repo root: ./k8s/deploy.sh
# Needs: minikube running (minikube start --driver=docker) and a .env copied from .env.example.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo ".env missing: cp .env.example .env and set passwords"; exit 1; }

echo "== Building images inside Minikube (works with the containerd runtime) =="
for svc in wallet toll-transaction vehicle-registry notification mock-bank; do
  minikube image build -t "toll-wallet/$svc:1.0" "services/$svc" | tail -1
done

echo "== Namespace, secret (from .env, never committed) and schema config maps =="
kubectl apply -f k8s/00-namespace.yaml
kubectl -n toll-wallet create secret generic db-credentials --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -
kubectl -n toll-wallet create configmap wallet-schema --from-file=services/wallet/schema.sql --dry-run=client -o yaml | kubectl apply -f -
kubectl -n toll-wallet create configmap toll-schema --from-file=services/toll-transaction/schema.sql --dry-run=client -o yaml | kubectl apply -f -
kubectl -n toll-wallet create configmap registry-schema --from-file=services/vehicle-registry/schema.sql --dry-run=client -o yaml | kubectl apply -f -

echo "== Databases and services =="
kubectl apply -f k8s/
kubectl -n toll-wallet rollout status deployment --timeout=300s
kubectl -n toll-wallet get pods -o wide
