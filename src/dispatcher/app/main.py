import os
from time import perf_counter

import httpx
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response
from fastapi.responses import JSONResponse
from app.bootstrap_helpers import DispatcherBootstrapper
from app.core.security import evaluate_authorization, get_access_profile_repository
from app.core.metrics import CONTENT_TYPE_LATEST, dispatcher_metrics
from app.core.database import logs_collection
from app.proxy_helpers import DispatcherProxyGateway
from app.route_registration import register_gateway_routes
from app.traffic_logging import DispatcherTrafficLogger

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8000")
PRODUCT_SERVICE_URL=os.getenv("PRODUCT_SERVICE_URL", "http://product_service:8000")
ORDER_SERVICE_URL=os.getenv("ORDER_SERVICE_URL", "http://order_service:8000")
AUTH_PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]

SERVICES={
    "auth":AUTH_SERVICE_URL,
    "products":PRODUCT_SERVICE_URL,
    "orders":ORDER_SERVICE_URL,
}
LOG_INSERT_TIMEOUT_SECONDS = float(os.getenv("DISPATCHER_LOG_INSERT_TIMEOUT_SECONDS", "0.2"))
PROXY_REQUEST_TIMEOUT_SECONDS = float(os.getenv("DISPATCHER_PROXY_TIMEOUT_SECONDS", "10.0"))

_proxy_gateway = DispatcherProxyGateway(
    auth_service_url=AUTH_SERVICE_URL,
    request_timeout_seconds=PROXY_REQUEST_TIMEOUT_SECONDS,
)
_traffic_logger = DispatcherTrafficLogger(insert_timeout_seconds=LOG_INSERT_TIMEOUT_SECONDS)
_bootstrapper = DispatcherBootstrapper(
    access_profile_repository_factory=lambda: get_access_profile_repository(),
)


def _service_unavailable_response() -> JSONResponse:
    return _proxy_gateway.service_unavailable_response()


def _internal_server_error_response() -> JSONResponse:
    return _proxy_gateway.internal_server_error_response()


def _is_upstream_failure(exc: Exception) -> bool:
    return _proxy_gateway.is_upstream_failure(exc)


def _proxy_exception_response(exc: Exception) -> JSONResponse:
    return _proxy_gateway.proxy_exception_response(exc)


def _build_auth_upstream_url(path: str) -> str:
    return _proxy_gateway.build_auth_upstream_url(path)


def _filtered_forward_headers(request: Request) -> dict[str, str]:
    return _proxy_gateway.filtered_forward_headers(request)


def _parse_upstream_payload(upstream_response: httpx.Response):
    return _proxy_gateway.parse_upstream_payload(upstream_response)


def _build_service_path(resource: str, path: str = "") -> str:
    return _proxy_gateway.build_service_path(resource, path)


def _build_proxy_response(status_code: int, payload):
    return _proxy_gateway.build_proxy_response(status_code, payload)


def _build_log_entry(request: Request, status_code: int):
    return _traffic_logger.build_log_entry(request, status_code)


async def _write_traffic_log(request: Request, status_code: int):
    await _traffic_logger.write(
        request,
        status_code,
        fallback_logs_collection=logs_collection,
    )


async def _build_logged_error_response(request: Request, status_code: int, message: str) -> JSONResponse:
    return await _traffic_logger.build_logged_error_response(
        request,
        status_code,
        message,
        fallback_logs_collection=logs_collection,
    )


def _record_request_metrics(request: Request, status_code: int, duration_seconds: float) -> None:
    dispatcher_metrics.record(request, status_code, duration_seconds)


def _finalize_metrics_recording(request: Request, response: Response, started_at: float) -> Response:
    _record_request_metrics(request, response.status_code, perf_counter() - started_at)
    return response


async def seed_dispatcher_access_profiles(app: FastAPI | None = None) -> None:
    await _bootstrapper.seed_dispatcher_access_profiles(app)


lifespan = _bootstrapper.build_lifespan()


async def forward_request(request:Request, base_url:str, path:str):
    return await _proxy_gateway.forward_request(request, base_url, path)
        
async def forward_auth_request(request: Request, path: str):
    return await _proxy_gateway.forward_auth_request(request, path)


async def _proxy_resource_request(request: Request, base_url: str, path: str):
    request_forwarder = getattr(request.app.state, "request_forwarder", forward_request)
    return await _proxy_gateway.proxy_resource_request(
        request,
        base_url,
        path,
        request_forwarder,
    )


async def check_auth(request: Request, call_next):
    started_at = perf_counter()
    status_code = await evaluate_authorization(request)
    if status_code == 401:
        response = await _build_logged_error_response(request, 401, "Unauthorized")
        return _finalize_metrics_recording(request, response, started_at)
    if status_code == 403:
        response = await _build_logged_error_response(request, 403, "Forbidden")
        return _finalize_metrics_recording(request, response, started_at)

    response= await call_next(request)
    await _write_traffic_log(request, response.status_code)
    return _finalize_metrics_recording(request, response, started_at)


def read_root():
    return {"message": "Dispatcher Gateway Running"}


def metrics():
    return Response(
        content=dispatcher_metrics.render_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

async def proxy_auth(path: str, request: Request):
    try:
        status_code, payload = await forward_auth_request(request, path) 
        return JSONResponse(status_code=status_code, content=payload)
    except httpx.RequestError as exc:
        return _proxy_exception_response(exc)
    except Exception as exc:
        return _proxy_exception_response(exc)
    

async def proxy_products(request: Request, path: str = ""):
    return await _proxy_resource_request(
        request,
        PRODUCT_SERVICE_URL,
        _build_service_path("products", path),
    )


async def proxy_products_root(request: Request):
    return await _proxy_resource_request(request, PRODUCT_SERVICE_URL, "products")



# @app.api_route("/orders/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
# async def proxy_orders(request: Request, path: str = ""):
#     status, payload = await forward_request(request, ORDER_SERVICE_URL, path)
#     return JSONResponse(status_code=status, content=payload)
async def proxy_orders(request: Request, path: str = ""):
    return await _proxy_resource_request(
        request,
        ORDER_SERVICE_URL,
        _build_service_path("orders", path),
    )

async def proxy_orders_root(request: Request):
    return await _proxy_resource_request(request, ORDER_SERVICE_URL, "orders")


def create_app(
    *,
    access_profile_repository=None,
    logs_collection=None,
    request_forwarder=None,
) -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    if access_profile_repository is not None:
        app.state.access_profile_repository = access_profile_repository
    if logs_collection is not None:
        app.state.logs_collection = logs_collection
    if request_forwarder is not None:
        app.state.request_forwarder = request_forwarder

    app.middleware("http")(check_auth)
    register_gateway_routes(
        app,
        read_root_handler=read_root,
        metrics_handler=metrics,
        proxy_auth_handler=proxy_auth,
        proxy_products_handler=proxy_products,
        proxy_products_root_handler=proxy_products_root,
        proxy_orders_handler=proxy_orders,
        proxy_orders_root_handler=proxy_orders_root,
        auth_proxy_methods=AUTH_PROXY_METHODS,
    )
    return app


app = create_app()
