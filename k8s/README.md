# Kubernetes (Minikube) deployment

The same images as Docker Compose, deployed to Minikube in the `toll-wallet` namespace.

| File | What it creates |
|---|---|
| `00-namespace.yaml` | namespace `toll-wallet` |
| `10-*-db.yaml` | one MySQL per service (wallet-db, toll-db, registry-db): PVC, Deployment (Recreate) and ClusterIP Service; schema mounted from a ConfigMap |
| `20-*.yaml` | Deployment and ClusterIP Service for each microservice, with readiness/liveness probes on `/health`, resource limits, and an init container that waits for the service's own database |
| `deploy.sh` | builds the images inside Minikube, creates the `db-credentials` Secret from your local `.env` (never committed) and the schema ConfigMaps, then applies everything and waits for rollout |
| `port-forward.sh` | exposes the five services on localhost:8001-8005 so the existing scripts run unchanged |

Service names match Compose (`wallet`, `toll-transaction`, ...), so inter-service URLs like `http://wallet:8001` work in both.

Replicas: toll-transaction 2, wallet 2, vehicle-registry 2 (stateless; all state is in MySQL), mock-bank 1 and notification 1 (they keep state in memory or SQLite inside the pod).

## Run
```bash
minikube start --driver=docker --cpus=4 --memory=3500
cp .env.example .env          # if not done yet
./k8s/deploy.sh
./k8s/port-forward.sh         # separate terminal; stop docker compose first so ports 8001-8005 are free
python scripts/e2e_test.py
```

## Useful commands
```bash
kubectl -n toll-wallet get pods,svc
kubectl -n toll-wallet logs deploy/toll-transaction -c toll-transaction
kubectl -n toll-wallet delete pod <toll-transaction-pod>      # self-healing
kubectl -n toll-wallet scale deploy/vehicle-registry --replicas=4
minikube delete                                              # remove the cluster
```

Evidence: `evidence/assignment2/k8s/`.
