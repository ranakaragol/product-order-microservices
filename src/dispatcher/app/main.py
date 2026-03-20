import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.access_control import AuthorizationService
from app.repositories.access_profile_repository import AccessProfileRepository
from app.gateway import router as gateway_router

app = FastAPI()
app.include_router(gateway_router)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("dispatcher")
_authorization_service = AuthorizationService(access_profile_repository=AccessProfileRepository())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        "critical_error request_id=%s method=%s path=%s error=%s",
        request_id,
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "request_id": request_id},
    )

@app.middleware("http")
async def check_auth(request: Request, call_next):
    request_id = uuid4().hex
    request.state.request_id = request_id
    started_at = time.perf_counter()

    logger.info(
        "incoming_request request_id=%s method=%s path=%s client=%s",
        request_id,
        request.method,
        request.url.path,
        request.client.host if request.client else "unknown",
    )

    decision = await _authorization_service.authorize_request(request)
    if not decision.allowed:
        logger.warning(
            "auth_failed request_id=%s method=%s path=%s reason=%s context=%s",
            request_id,
            request.method,
            request.url.path,
            decision.message,
            decision.context,
        )
        error_message = "Unauthorized" if decision.status_code == 401 else "Forbidden"
        return JSONResponse(status_code=decision.status_code, content={"error": error_message})

    request.state.auth_context = decision.context
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    user = decision.context.get("user", "anonymous")
    target_service = decision.context.get("target_service", "unknown")
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f user=%s target_service=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        user,
        target_service,
    )
    return response

@app.get("/")
def read_root():
    return {"message": "Dispatcher Gateway Running and Routing..."}
