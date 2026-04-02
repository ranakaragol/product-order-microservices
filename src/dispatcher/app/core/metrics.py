from fastapi import Request
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

REQUEST_LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class DispatcherMetrics:
    def __init__(self):
        self.reset()

    def reset(self):
        self.registry = CollectorRegistry()
        self.request_counter = Counter(
            "dispatcher_http_requests_total",
            "Total dispatcher requests labeled by method, route, and status code.",
            labelnames=("method", "route", "status_code"),
            registry=self.registry,
        )
        self.request_latency = Histogram(
            "dispatcher_http_request_duration_seconds",
            "Dispatcher request latency in seconds.",
            labelnames=("method", "route"),
            buckets=REQUEST_LATENCY_BUCKETS,
            registry=self.registry,
        )

    def record(self, request: Request, status_code: int, duration_seconds: float):
        route = self._resolve_route_label(request)
        if route == "/metrics":
            return

        method = request.method.upper()
        self.request_counter.labels(
            method=method,
            route=route,
            status_code=str(status_code),
        ).inc()
        self.request_latency.labels(method=method, route=route).observe(max(duration_seconds, 0.0))

    def render_latest(self) -> bytes:
        return generate_latest(self.registry)

    @staticmethod
    def _resolve_route_label(request: Request) -> str:
        return request.url.path


dispatcher_metrics = DispatcherMetrics()
