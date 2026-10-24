import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors import AppError
from app.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("wallet")

app = FastAPI(title="Wallet Service")


def error_body(request: Request, code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}}


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    logger.info("rid=%s %s %s", request.state.request_id, request.method, request.url.path)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status, content=error_body(request, exc.code, exc.message))


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=error_body(request, "VALIDATION_ERROR", str(exc.errors())))


@app.get("/health")
def health():
    return {"status": "ok", "service": "wallet"}

app.include_router(router)  # mount wallet endpoints
