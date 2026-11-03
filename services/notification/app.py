"""Mock notification service for the Hospital Appointment microservices demo.

This service owns notification.db and never reads another service's database.
Notifications are simulated and are not sent to a real email/SMS provider.
"""
import hashlib
import json
import logging
import os
import sqlite3
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

DB_PATH = os.getenv("DB_PATH", "notification.db")
NOTIFICATION_FAIL = os.getenv("NOTIFICATION_FAIL", "false").lower() == "true"
NOTIFICATION_DELAY_SECONDS = max(0.0, float(os.getenv("NOTIFICATION_DELAY_SECONDS", "0")))

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
logger = logging.getLogger("notification-service")
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

app = FastAPI(
    title="Hospital Appointment - Notification Service",
    description="Mock email/SMS notification API for appointment booking. No real messages are sent.",
    version="1.0.0",
)


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=20)
    connection.row_factory = sqlite3.Row
    return connection


with get_connection() as db:
    db.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            booking_id TEXT NOT NULL UNIQUE,
            message TEXT NOT NULL,
            recipient TEXT,
            channel TEXT NOT NULL DEFAULT 'mock',
            status TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            created_at TEXT NOT NULL,
            request_id TEXT NOT NULL
        )
    """)


class NotificationRequest(BaseModel):
    booking_id: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)
    recipient: Optional[str] = Field(default=None, max_length=200)
    channel: str = Field(default="mock", pattern="^(mock|email|sms)$")


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}, "request_id": request_id_ctx.get()}


@app.middleware("http")
async def correlation_and_logging(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_ctx.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(json.dumps({
            "event": "request_complete",
            "service": "notification",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }))
        return response
    finally:
        request_id_ctx.reset(token)


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        error = exc.detail
    else:
        error = {"code": "REQUEST_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": error, "request_id": request_id_ctx.get()})


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    logger.exception(json.dumps({"event": "unhandled_exception", "request_id": request_id_ctx.get()}))
    return JSONResponse(status_code=500, content=error_body("INTERNAL_ERROR", "An unexpected error occurred"))


@app.get("/health", tags=["operations"])
def health():
    return {"status": "UP", "service": "notification", "mode": "mock"}


@app.post("/api/v1/notifications", status_code=201, tags=["notifications"])
def create_notification(
    payload: NotificationRequest,
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID"),
):
    """Record a simulated notification. One notification is allowed per booking ID.

    Repeating the same booking/message replays the original record. Reusing a booking
    ID with different notification content is rejected with HTTP 409.
    """
    request_id = x_request_id or request_id_ctx.get()
    canonical = json.dumps(payload.model_dump(), sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # Failure/delay knobs make the downstream provider behaviour repeatable in demos.
    if NOTIFICATION_DELAY_SECONDS:
        time.sleep(NOTIFICATION_DELAY_SECONDS)
    if os.getenv("NOTIFICATION_FAIL", "false").lower() == "true":
        logger.warning(json.dumps({"event": "mock_provider_unavailable", "request_id": request_id, "booking_id": payload.booking_id}))
        raise HTTPException(status_code=503, detail={"code": "NOTIFICATION_PROVIDER_UNAVAILABLE", "message": "Mock notification provider is unavailable"})

    with get_connection() as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT * FROM notifications WHERE booking_id = ?", (payload.booking_id,)).fetchone()
        if existing:
            if existing["fingerprint"] != fingerprint:
                raise HTTPException(status_code=409, detail={"code": "BOOKING_NOTIFICATION_CONFLICT", "message": "A notification for this booking already exists with different content"})
            result = dict(existing)
            logger.info(json.dumps({"event": "notification_replay", "request_id": request_id, "booking_id": payload.booking_id, "notification_id": result["id"]}))
            return JSONResponse(status_code=200, content=result)

        result = {
            "id": str(uuid.uuid4()),
            "booking_id": payload.booking_id,
            "message": payload.message,
            "recipient": payload.recipient,
            "channel": payload.channel,
            "status": "SENT",  # simulated; no real provider is called
            "fingerprint": fingerprint,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
        }
        db.execute(
            "INSERT INTO notifications (id, booking_id, message, recipient, channel, status, fingerprint, created_at, request_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(result[key] for key in ("id", "booking_id", "message", "recipient", "channel", "status", "fingerprint", "created_at", "request_id")),
        )
        db.commit()

    logger.info(json.dumps({"event": "notification_recorded", "request_id": request_id, "booking_id": payload.booking_id, "notification_id": result["id"], "channel": payload.channel}))
    return JSONResponse(status_code=201, content=result)


@app.get("/api/v1/notifications", tags=["notifications"])
def list_notifications(limit: int = 100):
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail={"code": "INVALID_LIMIT", "message": "limit must be between 1 and 500"})
    with get_connection() as db:
        rows = db.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/v1/notifications/{notification_id}", tags=["notifications"])
def get_notification(notification_id: str):
    with get_connection() as db:
        row = db.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOTIFICATION_NOT_FOUND", "message": "Notification was not found"})
    return dict(row)
