# Scalable Services: Fleet Toll Wallet (Group 17)

A prepaid toll system for vehicle fleets, built as independent REST microservices, each with its own database. When a vehicle crosses a toll gate, the Toll Transaction service checks the vehicle in the Vehicle Registry, deducts the toll from the fleet's wallet via the Wallet service, and sends a notification.

Assignment 1: design and development. Assignment 2: containerization and deployment with Docker Compose.

## Services

| Service | Port | Database | Owner |
|---|---|---|---|
| wallet | 8001 | wallet_db (MySQL) | Poorva |
| toll-transaction | 8002 | toll_db (MySQL) | Poorva |
| vehicle-registry | 8003 | registry_db (MySQL) | Faheem |
| notification | 8004 | none | |
| mock-bank | 8005 | none (in-memory mock) | Faheem |

Each service lives in `services/<name>/` with its own Dockerfile, `schema.sql` (if it has a database) and README.

## Prerequisites

- Docker Desktop (or Docker Engine) with Docker Compose v2
- Check with: `docker --version` and `docker compose version`
- Free ports: 8001 to 8005

## Run the whole application

1. Clone the repository and open a terminal in its root folder.

2. Create your environment file from the template and set your own passwords:
   ```bash
   cp .env.example .env            # Windows PowerShell: Copy-Item .env.example .env
   ```
   `.env` is ignored by git. Never commit it.

3. Build and start everything:
   ```bash
   docker compose up --build
   ```
   The first build takes a few minutes. The databases start first. Each service waits for its database to be healthy before starting.

4. In a second terminal, check that every container is healthy:
   ```bash
   docker compose ps
   ```
   You can also open `http://localhost:8001/health` (and 8002 to 8005) in a browser.

## Try the main workflow

Run the demo script (it creates a wallet, tops it up, records a toll crossing, repeats it to show idempotency, and prints the balance):

```powershell
./scripts/demo.ps1
```

Or call the APIs yourself:

```bash
# 1. Create a wallet for a fleet
curl -X POST http://localhost:8001/api/v1/wallets -H "Content-Type: application/json" -d '{"fleet_id":"fleet-1"}'

# 2. Top it up with 1000.00 (amounts are integers in paise)
curl -X POST http://localhost:8001/api/v1/wallets/1/topup -H "Content-Type: application/json" -d '{"amount":100000,"reference_id":"top-1"}'

# 3. A vehicle crosses a toll gate (the vehicle must exist in the Vehicle Registry)
curl -X POST http://localhost:8002/api/v1/crossings -H "Content-Type: application/json" -H "Idempotency-Key: k1" -d '{"vehicle_id":"TRUCK-1","gate_id":"G1","amount":5000}'

# 4. Check the balance
curl http://localhost:8001/api/v1/wallets/1
```

Repeating step 3 with the same `Idempotency-Key` returns the original result and does not charge again.

API documentation: OpenAPI specs are in `docs/openapi/`, and each running service serves Swagger UI at `/docs`.

## Logs, health and debugging

```bash
docker compose ps                          # status and health of all containers
docker compose logs -f toll-transaction    # follow one service's logs
docker compose logs wallet toll-transaction  # one request ID (rid=...) appears in both services
docker inspect <container-name>            # full container details
docker compose exec wallet env             # check environment variables inside a container
```

## Stop and restart

```bash
docker compose down        # stop and remove containers; data is kept in Docker volumes
docker compose up          # start again; balances and crossings are still there
docker compose down -v     # stop AND delete all data (needed after changing a schema.sql)
```

## Configuration

All configuration comes from environment variables. Nothing is hard-coded in the images.

- `.env` (copied from `.env.example`) holds database users and passwords for Compose.
- `docker-compose.yml` passes each service its `DATABASE_URL` and the URLs of the services it calls. Inside Compose, services reach each other by service name (for example `http://wallet:8001`), not `localhost`.
- No secrets are committed or baked into images.

## Run a service without Docker (development)

See the README in each `services/<name>/` folder. In short: create a virtualenv, `pip install -r requirements.txt`, copy that service's `.env.example` to `.env`, load its `schema.sql` into MySQL, then run `uvicorn app.main:app --port <port>`.

## Run the tests

```bash
cd services/wallet && python -m pytest -v
cd services/toll-transaction && python -m pytest -v
cd services/vehicle-registry && python -m pytest -v
cd services/mock-bank && python -m pytest -v
```

## Challenge scripts (stack must be running)

```bash
python scripts/e2e_test.py                                # end-to-end: main transaction + failure paths
python evidence/challenge2/run_challenge2.py              # idempotency of POST /crossings
python evidence/challenge3/run_challenge3.py --stop-bank  # bank timeout, retry with backoff + jitter, clean failure
cd services/vehicle-registry && python -m pytest -v
cd services/mock-bank && python -m pytest -v
```

## Challenge scripts (stack must be running)

```bash
python evidence/challenge2/run_challenge2.py              # idempotency of POST /crossings
python evidence/challenge3/run_challenge3.py --stop-bank  # bank timeout, retry with backoff + jitter, clean failure
```

## Repository layout

```
docker-compose.yml     starts the complete application
.env.example           placeholder environment values (copy to .env)
services/<name>/       source, Dockerfile, schema.sql, tests
scripts/               demo and challenge scripts
docs/                  design documents and OpenAPI specs
evidence/              evidence for the challenges and deployment
```