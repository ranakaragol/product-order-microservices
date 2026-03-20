import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from app.core.security import evaluate_authorization

app= FastAPI()
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8000")


async def forward_auth_request(request: Request, path: str):
    url = f"{AUTH_SERVICE_URL.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        upstream_response = await client.request(
            method=request.method,
            url=url,
            params=request.query_params,
            content=await request.body(),
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
        )

    try:
        payload = upstream_response.json()
    except ValueError:
        payload = upstream_response.text

    return upstream_response.status_code, payload

@app.middleware("http")
async def check_auth(request: Request, call_next):
    status_code = evaluate_authorization(request)
    if status_code == 401:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    if status_code == 403:
        return JSONResponse(status_code=403, content={"error": "Forbidden"})
    
    #Her şey doğruysa veya rota başka bir yerse, isteğin geçmesine izin ver
    response= await call_next(request)
    return response

@app.get("/")
def read_root():
    return {"message": "Dispatcher Gateway Running"}


@app.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_auth(path: str, request: Request):
    try:
        status_code, payload = await forward_auth_request(request, path)
    except Exception:
        return JSONResponse(status_code=503, content={"error": "Service Unavailable"})

    if isinstance(payload, (dict, list)):
        return JSONResponse(status_code=status_code, content=payload)
    return Response(status_code=status_code, content=str(payload))
