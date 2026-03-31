import asyncio
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from app.core.security import evaluate_authorization, get_access_profile_repository
from fastapi import Request
from app.core.database import logs_collection
from app.models.log import TrafficLog

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


def _service_unavailable_response() -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": "Service Unavailable"})

def _build_auth_upstream_url(path: str) -> str:
    return f"{AUTH_SERVICE_URL.rstrip('/')}/{path.lstrip('/')}"


def _filtered_forward_headers(request: Request) -> dict[str, str]:
    return {k: v for k, v in request.headers.items() if k.lower() != "host"}


def _parse_upstream_payload(upstream_response: httpx.Response):
    try:
        return upstream_response.json()
    except ValueError:
        return upstream_response.text


def _build_service_path(resource: str, path: str = "") -> str:
    suffix = path.lstrip("/")
    return resource if not suffix else f"{resource}/{suffix}"


def _build_proxy_response(status_code: int, payload):
    if status_code == 204 or payload is None:
        return Response(status_code=status_code)

    return JSONResponse(status_code=status_code, content=payload)


def _build_log_entry(request: Request, status_code: int) -> TrafficLog:
    path_parts = request.url.path.strip("/").split("/")
    service_name = path_parts[0] if path_parts else "root"
    return TrafficLog(
        method=request.method,
        path=request.url.path,
        service=service_name,
        status_code=status_code,
        client_ip=request.client.host if request.client else "unknown",
    )


async def _write_traffic_log(request: Request, status_code: int):
    try:
        log_entry = _build_log_entry(request, status_code)
        await asyncio.wait_for(
            logs_collection.insert_one(log_entry.model_dump()),
            timeout=LOG_INSERT_TIMEOUT_SECONDS,
        )
    except Exception as e:
        print(f"Logging error: {e}")


async def _build_logged_error_response(request: Request, status_code: int, message: str) -> JSONResponse:
    await _write_traffic_log(request, status_code)
    return JSONResponse(status_code=status_code, content={"error": message})


async def seed_dispatcher_access_profiles() -> None:
    await get_access_profile_repository().seed_bootstrap_profiles()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_dispatcher_access_profiles()
    yield


app = FastAPI(lifespan=lifespan)


async def forward_request(request:Request, base_url:str, path:str):
    # """Genel mikroservis yönlendirme fonksiyonu"""
    # url = f"{base_url.rstrip('/')}/{request.url.path.lstrip('/')}"
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            upstream_response = await client.request(
                method=request.method,
                url=url,
                params=request.query_params,
                content=await request.body(),
                headers=_filtered_forward_headers(request),
            )
            return upstream_response.status_code, _parse_upstream_payload(upstream_response)
        except httpx.RequestError as e:
            print(f"DEBUG: Error in forward -> {e}")
            return 503, {"error": "Service Unavailable"}
        
async def forward_auth_request(request: Request, path: str):
    url = _build_auth_upstream_url(path)
    async with httpx.AsyncClient(timeout=10.0) as client:
        upstream_response = await client.request(
            method=request.method,
            url=url,
            params=request.query_params,
            content=await request.body(),
            headers=_filtered_forward_headers(request),
        )

    payload = _parse_upstream_payload(upstream_response)
    return upstream_response.status_code, payload


async def _proxy_resource_request(request: Request, base_url: str, path: str):
    try:
        status, payload = await forward_request(request, base_url, path)
        return _build_proxy_response(status, payload)
    except Exception:
        return _service_unavailable_response()


@app.middleware("http")
async def check_auth(request: Request, call_next):
    
    status_code = await evaluate_authorization(request)
    if status_code == 401:
        return await _build_logged_error_response(request, 401, "Unauthorized")
    if status_code == 403:
        return await _build_logged_error_response(request, 403, "Forbidden")
    response= await call_next(request)
    await _write_traffic_log(request, response.status_code)
    return response


@app.get("/")
def read_root():
    return {"message": "Dispatcher Gateway Running"}

@app.api_route("/auth/{path:path}", methods=AUTH_PROXY_METHODS)
async def proxy_auth(path: str, request: Request):
    try:
        status_code, payload = await forward_auth_request(request, path) 
        return JSONResponse(status_code=status_code, content=payload)
    except Exception:
        return _service_unavailable_response()
    

@app.api_route("/products/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_products(request: Request, path: str = ""):
    return await _proxy_resource_request(
        request,
        PRODUCT_SERVICE_URL,
        _build_service_path("products", path),
    )


@app.api_route("/products", methods=["GET", "POST"])
async def proxy_products_root(request: Request):
    return await _proxy_resource_request(request, PRODUCT_SERVICE_URL, "products")



# @app.api_route("/orders/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
# async def proxy_orders(request: Request, path: str = ""):
#     status, payload = await forward_request(request, ORDER_SERVICE_URL, path)
#     return JSONResponse(status_code=status, content=payload)
@app.api_route("/orders/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy_orders(request: Request, path: str = ""):
    return await _proxy_resource_request(
        request,
        ORDER_SERVICE_URL,
        _build_service_path("orders", path),
    )

@app.api_route("/orders", methods=["GET", "POST"])
async def proxy_orders_root(request: Request):
    return await _proxy_resource_request(request, ORDER_SERVICE_URL, "orders")
