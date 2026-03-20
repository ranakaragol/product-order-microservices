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
    if status_code != 200:
        error_msg = "Unauthorized" if status_code == 401 else "Forbidden"
        return JSONResponse(status_code=status_code, content={"error": error_msg})
    
    path_parts = request.url.path.strip("/").split("/")
    service_name = path_parts[0] if path_parts else ""
    
    if service_name in SERVICES:
        base_url = SERVICES[service_name]
        remaining_path = "/".join(path_parts[1:])
        
        try: 
            if service_name == "auth":
                status, payload = await forward_auth_request(request, remaining_path)
            else:
                status, payload = await forward_request(request, base_url, remaining_path)
            return JSONResponse(status_code=status, content=payload)
        except Exception: #Herhangi bir hata olursa 503 döner
            return JSONResponse(status_code=503, content={"error": "Service Unavailable"})
    
    if service_name != "" and request.url.path != "/":
        return JSONResponse(status_code=404, content={"error": "Not Found"})
    
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