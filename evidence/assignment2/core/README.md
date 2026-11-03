# Assignment 2, Tasks 1 and 2: containerization and Docker Compose evidence

All of this comes from `docker compose up --build` on the repository as committed (after the Task 3 fix).

| Requirement | Evidence |
|---|---|
| One Dockerfile and image per service | `01_images_built.txt`: five images (wallet, toll-transaction, vehicle-registry, notification, mock-bank) |
| Databases run as containers | `02_containers_running.txt`: wallet-db, toll-db, registry-db (mysql:8.0), each with its own user and volume |
| All services running and healthy | `02_containers_running.txt`: 8 containers `(healthy)` |
| Config from environment variables, no secrets in images | `03_config_from_env.txt`: DATABASE_URL and BANK_* come from Compose (password masked); the image contains only `app/` and `requirements.txt`, no `.env` |
| Communication between services | `04_interservice_trace.txt`: one `X-Request-ID` appears in toll-transaction, vehicle-registry, wallet and notification logs; services reach each other by Compose service name (`http://wallet:8001`, ...) |
| Main workflow | `04_interservice_trace.txt` (crossing COMPLETED, balance 30000 to 25000) and `scripts/e2e_test.py` (18 checks, `evidence/e2e/run_output.txt`) |
| Logs and health status | `04_interservice_trace.txt`, `02_containers_running.txt`, Task 3 diagnosis |
| Stop and restart | `05_stop_restart.txt`: `docker compose down`, then `up`; the wallet and vehicle are still there (named volumes) and the end-to-end test passes again |

Known gap: notification answers the toll service with 422, because of a body-shape mismatch in the notification application (see `../task3/README.md`, section 4). Crossings still complete, because notification is best effort.
