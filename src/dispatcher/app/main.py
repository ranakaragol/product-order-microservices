import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from app.core.security import evaluate_authorization
from fastapi import Depends, Request, APIRouter

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
    """Genel mikroservis yönlendirme fonksiyonu"""
    url=f"{base_url.rstrip('/')}/{path.lstrip('/')}".rstrip("/")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            upstream_response=await client.request(
                method=request.method,
                url=url,
                params=request.query_params,
                content=await request.body(),
                headers= _filtered_forward_headers(request),
            )
            return upstream_response.status_code, _parse_upstream_payload(upstream_response)
        except Exception:
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
    return await call_next(request)

@app.get("/")
def read_root():
    return {"message": "Dispatcher Gateway Running"}

@app.api_route("/auth/{path:path}", methods=AUTH_PROXY_METHODS)
async def proxy_auth(path: str, request: Request):
    try:
        status_code, payload = await forward_auth_request(request, path) 
        return JSONResponse(status_code=status_code, content=payload)
    except Exception:
        return JSONResponse(status_code=503, content={"error": "Service Unavailable"})
    
@app.api_route("/products", methods=["GET", "POST"])
async def proxy_products_root(request: Request):
    status, payload = await forward_request(request, PRODUCT_SERVICE_URL, "")
    return JSONResponse(status_code=status, content=payload)

@app.api_route("/products/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_products(request: Request, path: str = ""):
    status, payload = await forward_request(request, PRODUCT_SERVICE_URL, path)
    return JSONResponse(status_code=status, content=payload)

@app.api_route("/orders", methods=["GET", "POST"])
async def proxy_orders_root(request: Request):
    status, payload = await forward_request(request, ORDER_SERVICE_URL, "")
    return JSONResponse(status_code=status, content=payload)

@app.api_route("/orders/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_orders(request: Request, path: str = ""):
    status, payload = await forward_request(request, ORDER_SERVICE_URL, path)
    return JSONResponse(status_code=status, content=payload)

"""@app.api_route("/{path:path}")
async def catch_all():
    return JSONResponse(status_code=404, content={"error": "Not Found"})"""