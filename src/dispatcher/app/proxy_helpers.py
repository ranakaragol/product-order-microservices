import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse


class DispatcherProxyGateway:
    def __init__(self, *, auth_service_url: str, request_timeout_seconds: float = 10.0):
        self._auth_service_url = auth_service_url
        self._request_timeout_seconds = request_timeout_seconds
        self._client = httpx.AsyncClient(
            timeout=self._request_timeout_seconds,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
        )

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def service_unavailable_response() -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": "Service Unavailable"})

    @staticmethod
    def internal_server_error_response() -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})

    @staticmethod
    def is_upstream_failure(exc: Exception) -> bool:
        return isinstance(exc, httpx.RequestError)

    def proxy_exception_response(self, exc: Exception) -> JSONResponse:
        if self.is_upstream_failure(exc):
            return self.service_unavailable_response()

        return self.internal_server_error_response()

    def build_auth_upstream_url(self, path: str) -> str:
        return f"{self._auth_service_url.rstrip('/')}/{path.lstrip('/')}"

    @staticmethod
    def filtered_forward_headers(request: Request) -> dict[str, str]:
        return {k: v for k, v in request.headers.items() if k.lower() != "host"}

    @staticmethod
    def parse_upstream_payload(upstream_response: httpx.Response):
        try:
            return upstream_response.json()
        except ValueError:
            return upstream_response.text

    @staticmethod
    def build_service_path(resource: str, path: str = "") -> str:
        suffix = path.lstrip("/")
        return resource if not suffix else f"{resource}/{suffix}"

    @staticmethod
    def build_proxy_response(status_code: int, payload):
        if status_code == 204 or payload is None:
            return Response(status_code=status_code)

        return JSONResponse(status_code=status_code, content=payload)

    async def forward_request(self, request: Request, base_url: str, path: str):
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            upstream_response = await self._client.request(
                method=request.method,
                url=url,
                params=request.query_params,
                content=await request.body(),
                headers=self.filtered_forward_headers(request),
            )
            return upstream_response.status_code, self.parse_upstream_payload(upstream_response)
        except httpx.RequestError as exc:
            print(f"DEBUG: Error in forward -> {exc}")
            return 503, {"error": "Service Unavailable"}

    async def forward_auth_request(self, request: Request, path: str):
        url = self.build_auth_upstream_url(path)
        upstream_response = await self._client.request(
            method=request.method,
            url=url,
            params=request.query_params,
            content=await request.body(),
            headers=self.filtered_forward_headers(request),
        )

        payload = self.parse_upstream_payload(upstream_response)
        return upstream_response.status_code, payload

    async def proxy_resource_request(self, request: Request, base_url: str, path: str, request_forwarder):
        try:
            status, payload = await request_forwarder(request, base_url, path)
            return self.build_proxy_response(status, payload)
        except httpx.RequestError as exc:
            return self.proxy_exception_response(exc)
        except Exception as exc:
            return self.proxy_exception_response(exc)
