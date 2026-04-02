import asyncio

from fastapi import Request
from fastapi.responses import JSONResponse

from app.models.log import TrafficLog


class DispatcherTrafficLogger:
    def __init__(self, *, insert_timeout_seconds: float):
        self._insert_timeout_seconds = insert_timeout_seconds

    @staticmethod
    def build_log_entry(request: Request, status_code: int) -> TrafficLog:
        path_parts = request.url.path.strip("/").split("/")
        service_name = path_parts[0] if path_parts else "root"
        return TrafficLog(
            method=request.method,
            path=request.url.path,
            service=service_name,
            status_code=status_code,
            client_ip=request.client.host if request.client else "unknown",
        )

    async def write(self, request: Request, status_code: int, fallback_logs_collection):
        try:
            log_entry = self.build_log_entry(request, status_code)
            target_logs_collection = getattr(request.app.state, "logs_collection", fallback_logs_collection)
            await asyncio.wait_for(
                target_logs_collection.insert_one(log_entry.model_dump()),
                timeout=self._insert_timeout_seconds,
            )
        except Exception as exc:
            print(f"Logging error: {exc}")

    async def build_logged_error_response(
        self,
        request: Request,
        status_code: int,
        message: str,
        fallback_logs_collection,
    ) -> JSONResponse:
        await self.write(request, status_code, fallback_logs_collection)
        return JSONResponse(status_code=status_code, content={"error": message})
