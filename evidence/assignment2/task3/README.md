# Assignment 2, Task 3: deployment troubleshooting

A genuine problem we hit when bringing the whole application up with `docker compose up --build` for the first time. Every service had worked on its own during development.

## 1. Problem (symptom)
`docker compose up --build` did not start the application, and it failed in two stages:

1. The build stopped with `"/requirements.txt": not found` at `[notification 3/5] COPY requirements.txt .` (`01_symptom_build.txt`).
2. After that was fixed, every image built, but Compose stopped with `dependency failed to start: container ...-notification-1 is unhealthy`. `toll-transaction` stayed in `Created`, so the main workflow (a toll crossing) could not run at all (`03_symptom_unhealthy.txt`).

## 2. Diagnosis
| Step | Command | What it showed |
|---|---|---|
| Build failure | `ls services/notification`, `grep COPY Dockerfile` | The Dockerfile copies `requirements.txt`, but the file was never committed; it only existed on the developer's machine (`02_diagnosis_missing_requirements.txt`) |
| Which container | `docker compose ps -a` | notification `Up (unhealthy)` with ports `8000/tcp, 0.0.0.0:8004->8004/tcp`; toll-transaction only `Created` |
| Why unhealthy | `docker inspect --format '{{json .State.Health}}'` | Health probe on `localhost:8004/health`: `Connection refused`, FailingStreak 6 |
| What the app is doing | `docker compose logs notification` | `Uvicorn running on http://0.0.0.0:8000`: the app is up, but on the wrong port |
| Confirm | `docker compose exec notification ... urlopen('http://localhost:8000/health')` | `{"status":"UP"}` on 8000 |
| Compare with config | `grep 8000 Dockerfile`, `docker-compose.yml` | Dockerfile `EXPOSE 8000` / `--port 8000`; Compose maps and probes 8004, the port in `docs/contract.md` |

All of this is in `04_diagnosis_port.txt`.

**Root cause:** the image did not match the deployment contract. A dependency file was missing from the repository, and the service listened on 8000 while Compose, the healthcheck and every caller expected 8004. Because `toll-transaction` has `depends_on: notification: condition: service_healthy`, one wrong port blocked the whole application.

## 3. Solution and validation
- Added `services/notification/requirements.txt` with pinned versions matching the other services.
- Changed the notification Dockerfile to `EXPOSE 8004` and `--port 8004`.
- Added `services/notification/.dockerignore` so the local `notification.db` and `.env` are never copied into the image.

Validation (`05_fix_and_validation.txt`): `docker compose up --build -d --wait` succeeds; all 8 containers are `healthy`; `curl localhost:8004/health` answers; `scripts/e2e_test.py` passes 18 of 18 checks across all five services.

## 4. Further finding (not yet fixed)
With the container healthy, the logs show the notification service answering the toll service's `POST /api/v1/notifications` with **422**. The request ID `e2e-ok-...` arrives, so the network path works. The cause is the request body: the service still expects the `{booking_id, message}` shape from another project, while the contract is `{wallet_id, type, message}`. Toll crossings still complete, because notification is best effort by design, but no toll notification is stored. Fixing this means changing the notification application code, which its owner is doing.

## 5. Learning reflection
"It works on my machine" hid two things a container cannot hide: files that were never committed, and an assumed port. A healthcheck turned a silent mismatch into a loud, early failure. Without it, toll-transaction would have started and every notification would have failed quietly. In a real deployment I would (1) build images in CI from a clean checkout, so a missing file fails the build before anyone deploys, (2) read the port from one environment variable used by the app, the Dockerfile and the orchestrator, and (3) keep healthchecks and `depends_on: service_healthy`, and also add a contract test for each service-to-service call, because a healthy container can still speak the wrong API.
