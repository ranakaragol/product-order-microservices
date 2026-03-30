import asyncio
import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.core.security import evaluate_authorization
from fastapi import Request
from app.core.database import logs_collection
from app.models.log import TrafficLog

app= FastAPI()
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


@app.middleware("http")
async def check_auth(request: Request, call_next):
    
    status_code = evaluate_authorization(request)
    if status_code == 401:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    if status_code == 403:
        return JSONResponse(status_code=403, content={"error": "Forbidden"})
    response= await call_next(request)

    try:
        path_parts=request.url.path.strip("/").split("/")
        service_name=path_parts[0] if path_parts else "root"

        log_entry= TrafficLog(
            method=request.method,
            path=request.url.path,
            service=service_name,
            status_code=response.status_code,
            client_ip= request.client.host if request.client else "unknown"
        )
        await asyncio.wait_for(
            logs_collection.insert_one(log_entry.model_dump()),
            timeout=LOG_INSERT_TIMEOUT_SECONDS,
        )
    except Exception as e:
        print(f"Logging error: {e}")

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
    full_path = f"products/{path}"
    try:
        status, payload = await forward_request(request, PRODUCT_SERVICE_URL, full_path)
        return JSONResponse(status_code=status, content=payload)
    except Exception:
        return _service_unavailable_response()


@app.api_route("/products", methods=["GET", "POST"])
async def proxy_products_root(request: Request):
    # Boş string yerine "products" gönderiyoruz
    status, payload = await forward_request(request, PRODUCT_SERVICE_URL, "products")
    return JSONResponse(status_code=status, content=payload)



# @app.api_route("/orders/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
# async def proxy_orders(request: Request, path: str = ""):
#     status, payload = await forward_request(request, ORDER_SERVICE_URL, path)
#     return JSONResponse(status_code=status, content=payload)
@app.api_route("/orders/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy_orders(request: Request, path: str = ""):
    full_path = f"orders/{path}"
    try:
        status, payload = await forward_request(request, ORDER_SERVICE_URL, full_path)
        return JSONResponse(status_code=status, content=payload)
    except Exception:
        return _service_unavailable_response()

@app.api_route("/orders", methods=["GET", "POST"])
async def proxy_orders_root(request: Request):
    try:
        status, payload = await forward_request(request, ORDER_SERVICE_URL, "orders")
        return JSONResponse(status_code=status, content=payload)
    except Exception:
        return _service_unavailable_response()
