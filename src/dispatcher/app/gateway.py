import os
import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8001")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8002")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")

router = APIRouter()


class RequestForwarder:
    """Forwards incoming requests to target microservices."""

    _blocked_headers = {"host", "content-length", "connection"}

    def _forward_headers(self, request: Request) -> dict:
        return {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in self._blocked_headers
        }

    async def forward(self, method: str, url: str, request: Request) -> JSONResponse:
        try:
            async with httpx.AsyncClient() as client:
                body = await request.body()
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self._forward_headers(request),
                    content=body,
                )

            try:
                resp_content = response.json()
            except Exception:
                resp_content = {"detail": response.text}

            return JSONResponse(status_code=response.status_code, content=resp_content)

        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hedef servise şu an ulaşılamıyor (Service Unavailable).",
            )


request_forwarder = RequestForwarder()


async def forward_request(method: str, url: str, request: Request):
    """Backwards-compatible forwarding wrapper used by route handlers."""
    return await request_forwarder.forward(method=method, url=url, request=request)


@router.api_route("/products/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_products(path: str, request: Request):
    url = f"{PRODUCT_SERVICE_URL}/products/{path}"
    return await forward_request(request.method, url, request)


@router.api_route("/products", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_products_root(request: Request):
    url = f"{PRODUCT_SERVICE_URL}/products"
    return await forward_request(request.method, url, request)


@router.api_route("/orders/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_orders(path: str, request: Request):
    url = f"{ORDER_SERVICE_URL}/orders/{path}"
    return await forward_request(request.method, url, request)


@router.api_route("/orders", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_orders_root(request: Request):
    url = f"{ORDER_SERVICE_URL}/orders"
    return await forward_request(request.method, url, request)


@router.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def route_auth(path: str, request: Request):
    url = f"{AUTH_SERVICE_URL}/{path}"
    return await forward_request(request.method, url, request)
