# Assignment 2, advanced: observability with Prometheus and Grafana

Start: `docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build`
Prometheus: http://localhost:9090 (Status > Targets). Grafana: http://localhost:3000, dashboard "Fleet Toll Wallet" (provisioned automatically).

## What is measured
| Metric | Source | Why it is useful |
|---|---|---|
| `up` | Prometheus scrape | which services are reachable |
| `http_requests_total{service,method,route,status}` | `app/metrics.py` middleware in wallet, toll-transaction, vehicle-registry, mock-bank | traffic and error rate per service and route; routes are templates (`/api/v1/wallets/{wallet_id}`), so label cardinality stays low |
| `http_request_duration_seconds` (histogram) | same middleware | p95 latency per service |
| `bank_collect_attempts_total{outcome}` | wallet `bank_client.py` | Challenge 3A made visible: ok, http_503, timeout, connection_error per attempt |
| `bank_collect_results_total{result}` | wallet `bank_client.py` | success, success_after_retry, gave_up, rejected |

## Evidence
- `01_metrics.txt`: all 4 targets `up`; request counts per service; errors by status (mock-bank 503 from fail/flaky mode, wallet 502 clean give-ups, toll 409/404 failure paths); bank attempts `http_503=10, timeout=4, ok=3` and results `success=2, success_after_retry=1, gave_up=3` after running the end-to-end and Challenge 3 scripts; p95 latency shows the slow-bank scenario (wallet about 7 s, i.e. timeouts plus backoff) against about 10 ms for toll-transaction.
- `02_grafana_dashboard.jpg`: the dashboard during that run.

Not instrumented: notification (owned by another team member), and the MySQL containers.
