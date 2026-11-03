import time

from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, make_asgi_app

# Request count and latency per route, scraped by Prometheus from /metrics
REQUESTS = Counter("http_requests_total", "HTTP requests handled", ["service", "method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["service", "route"],
                    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))


def install(app: FastAPI, service: str) -> None:
    # Record every request except the scrape itself, labelled by route template (not raw path)
    @app.middleware("http")
    async def record_metrics(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        route = getattr(request.scope.get("route"), "path", "unmatched")
        if not request.url.path.startswith("/metrics"):
            REQUESTS.labels(service, request.method, route, response.status_code).inc()
            LATENCY.labels(service, route).observe(time.perf_counter() - start)
        return response

    app.mount("/metrics", make_asgi_app())
