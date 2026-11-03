"""Mock notification service for the Fleet Toll Wallet.

This service owns notification.db (SQLite) and never reads another service's database.
Notifications are simulated: they are stored and logged, never sent to a real email/SMS provider.
"""
import json
import logging
import os
import sqlite3
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

DB_PATH = os.getenv("DB_PATH", "notification.db")
NOTIFICATION_DELAY_SECONDS = max(0.0, float(os.getenv("NOTIFICATION_DELAY_SECONDS", "0")))

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
logger = logging.getLogger("notification-service")
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

app = FastAPI(
    title="Fleet Toll Wallet - Notification Service",
    description="Mock notifications for toll charges and low wallet balance. No real messages are sent.",
    version="2.0.0",
)


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=20)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with get_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                wallet_id INTEGER NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('TOLL_CHARGED', 'LOW_BALANCE')),
                message TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'mock',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                request_id TEXT NOT NULL
            )
        """)
        # BR6 state: a wallet is in this table while it has an unresolved LOW_BALANCE alert
        db.execute("""
            CREATE TABLE IF NOT EXISTS low_balance_alerts (
                wallet_id INTEGER PRIMARY KEY,
                notification_id TEXT NOT NULL REFERENCES notifications(id),
                opened_at TEXT NOT NULL
            )
        """)


init_db()


class NotificationRequest(BaseModel):
    wallet_id: int = Field(gt=0)
    type: Literal["TOLL_CHARGED", "LOW_BALANCE"]
    message: str = Field(min_length=1, max_length=500)


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id_ctx.get()}}


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
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.detail["code"], exc.detail["message"]))
    return JSONResponse(status_code=exc.status_code, content=error_body("REQUEST_ERROR", str(exc.detail)))


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=error_body("VALIDATION_ERROR", str(exc.errors())))


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    logger.exception(json.dumps({"event": "unhandled_exception", "request_id": request_id_ctx.get()}))
    return JSONResponse(status_code=500, content=error_body("INTERNAL_ERROR", "An unexpected error occurred"))


@app.get("/health", tags=["operations"])
def health():
    return {"status": "ok", "service": "notification", "mode": "mock"}


@app.post("/api/v1/notifications", status_code=201, tags=["notifications"])
def create_notification(payload: NotificationRequest, x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID")):
    """Store and log a simulated notification.

    BR6: only one LOW_BALANCE notification per wallet until its balance recovers. A later
    TOLL_CHARGED for the wallet shows the balance covered a toll again, which closes the alert.
    A suppressed LOW_BALANCE returns 200 with the original notification and "suppressed": true.
    """
    request_id = x_request_id or request_id_ctx.get()
    if NOTIFICATION_DELAY_SECONDS:  # knob to simulate a slow provider in demos
        time.sleep(NOTIFICATION_DELAY_SECONDS)
    if os.getenv("NOTIFICATION_FAIL", "false").lower() == "true":
        logger.warning(json.dumps({"event": "mock_provider_unavailable", "request_id": request_id, "wallet_id": payload.wallet_id}))
        raise HTTPException(status_code=503, detail={"code": "NOTIFICATION_PROVIDER_UNAVAILABLE", "message": "Mock notification provider is unavailable"})

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as db:
        db.execute("BEGIN IMMEDIATE")  # serialise writers so two LOW_BALANCE alerts cannot both open
        if payload.type == "LOW_BALANCE":
            open_alert = db.execute("SELECT notification_id FROM low_balance_alerts WHERE wallet_id = ?", (payload.wallet_id,)).fetchone()
            if open_alert:
                original = dict(db.execute("SELECT * FROM notifications WHERE id = ?", (open_alert["notification_id"],)).fetchone())
                logger.info(json.dumps({"event": "low_balance_suppressed", "request_id": request_id, "wallet_id": payload.wallet_id,
                                        "open_notification_id": original["id"]}))
                return JSONResponse(status_code=200, content={**original, "suppressed": True})

        result = {"id": str(uuid.uuid4()), "wallet_id": payload.wallet_id, "type": payload.type, "message": payload.message,
                  "channel": "mock", "status": "SENT", "created_at": now, "request_id": request_id}
        db.execute("INSERT INTO notifications (id, wallet_id, type, message, channel, status, created_at, request_id) "
                   "VALUES (:id, :wallet_id, :type, :message, :channel, :status, :created_at, :request_id)", result)
        if payload.type == "LOW_BALANCE":
            db.execute("INSERT INTO low_balance_alerts (wallet_id, notification_id, opened_at) VALUES (?, ?, ?)",
                       (payload.wallet_id, result["id"], now))
        else:  # a successful toll charge means the balance has recovered
            db.execute("DELETE FROM low_balance_alerts WHERE wallet_id = ?", (payload.wallet_id,))
        db.commit()

    logger.info(json.dumps({"event": "notification_recorded", "request_id": request_id, "wallet_id": payload.wallet_id,
                            "type": payload.type, "notification_id": result["id"], "message": payload.message}))
    return JSONResponse(status_code=201, content={**result, "suppressed": False})


@app.get("/api/v1/notifications", tags=["notifications"])
def list_notifications(wallet_id: Optional[int] = None, type: Optional[str] = None, limit: int = 100):
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail={"code": "INVALID_LIMIT", "message": "limit must be between 1 and 500"})
    sql, params = "SELECT * FROM notifications WHERE 1=1", []
    if wallet_id is not None:
        sql, params = sql + " AND wallet_id = ?", params + [wallet_id]
    if type is not None:
        sql, params = sql + " AND type = ?", params + [type]
    with get_connection() as db:
        rows = db.execute(sql + " ORDER BY created_at DESC LIMIT ?", params + [limit]).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/v1/notifications/{notification_id}", tags=["notifications"])
def get_notification(notification_id: str):
    with get_connection() as db:
        row = db.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOTIFICATION_NOT_FOUND", "message": "Notification was not found"})
    return dict(row)
