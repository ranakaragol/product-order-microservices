from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt

from app.main import create_app

SECRET_KEY = "yazlab-secret-key"


class FakeAccessProfileRepository:
    async def seed_bootstrap_profiles(self):
        return None

    async def get_profile_by_subject(self, subject: str):
        if not subject:
            return None

        return {
            "subject": subject,
            "permissions": [
                {
                    "resource": "/products",
                    "methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                },
                {
                    "resource": "/orders",
                    "methods": ["GET", "POST", "PATCH", "DELETE"],
                },
            ],
        }


class FakeLogsCollection:
    def __init__(self):
        self.entries = []

    async def insert_one(self, document):
        self.entries.append(dict(document))
        return {"acknowledged": True}


def _token(subject: str = "dispatcher-user") -> str:
    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _build_test_app():
    async def fake_forward(request, base_url, path):
        if path == "products":
            return 200, [{"id": "p-metrics"}]
        return 404, {"detail": "not found"}

    return create_app(
        access_profile_repository=FakeAccessProfileRepository(),
        logs_collection=FakeLogsCollection(),
        request_forwarder=fake_forward,
    )


def test_metrics_endpoint_returns_prometheus_plain_text():
    app = _build_test_app()

    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "dispatcher_http_requests_total" in response.text


def test_product_request_increments_counter_with_labels():
    app = _build_test_app()
    headers = {"Authorization": f"Bearer {_token()}"}

    with TestClient(app) as client:
        upstream_response = client.get("/products", headers=headers)
        metrics_response = client.get("/metrics")

    assert upstream_response.status_code == 200
    assert metrics_response.status_code == 200
    assert 'dispatcher_http_requests_total{method="GET",route="/products",status_code="200"} 1.0' in metrics_response.text


def test_request_latency_histogram_is_exposed_for_dispatcher_requests():
    app = _build_test_app()
    headers = {"Authorization": f"Bearer {_token()}"}

    with TestClient(app) as client:
        client.get("/products", headers=headers)
        metrics_response = client.get("/metrics")

    assert metrics_response.status_code == 200
    assert "dispatcher_http_request_duration_seconds_bucket" in metrics_response.text
    assert 'dispatcher_http_request_duration_seconds_count{method="GET",route="/products"} 1.0' in metrics_response.text


def test_metrics_endpoint_does_not_count_itself_as_application_traffic_noise():
    app = _build_test_app()

    with TestClient(app) as client:
        first_metrics = client.get("/metrics")
        second_metrics = client.get("/metrics")

    assert first_metrics.status_code == 200
    assert second_metrics.status_code == 200
    assert 'route="/metrics"' not in second_metrics.text
