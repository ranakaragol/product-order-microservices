import pytest 
import json
import httpx
from httpx import ASGITransport,AsyncClient
from app.main import app
import app.main as dispatcher_main

pytestmark=pytest.mark.asyncio(loop_scope="function")

async def test_missing_token_returns_401():
    """Header'da token yoksa dispatcher 401 dönmeli"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response=await ac.get("/products/list")
        assert response.status_code==401
        assert response.json()=={"error": "Unauthorized"}

async def test_invalid_token_returns_401():
    """Header'da geçersiz bir token varsa 401 dönmeli"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response=await ac.get("/products/list", headers={"Authorization": "Bearer sahte_token_123"})
        assert response.status_code==401

async def test_routing_to_unknown_service_returns_404():
    """Bilinmeyen bir mikroservis istek gelirse 404 dönmeli"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response= await ac.get("/olmayanservis/test")
        assert response.status_code==404


class DummyResponse:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class DummyAsyncClient:
    def __init__(self, request_impl):
        self._request_impl = request_impl

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, headers=None, content=None):
        return await self._request_impl(method, url, headers=headers, content=content)


async def test_auth_forwarding_passes_upstream_status_and_json(monkeypatch):
    async def request_impl(method, url, headers=None, content=None):
        assert method == "POST"
        assert url.endswith("/login")
        return DummyResponse(422, payload={"detail": "bad payload"})

    monkeypatch.setattr(
        dispatcher_main.httpx,
        "AsyncClient",
        lambda: DummyAsyncClient(request_impl),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/auth/login", json={"username": "u", "password": "p"})

    assert response.status_code == 422
    assert response.json() == {"detail": "bad payload"}


async def test_auth_forwarding_returns_503_when_upstream_unreachable(monkeypatch):
    async def request_impl(method, url, headers=None, content=None):
        raise httpx.RequestError("service down")

    monkeypatch.setattr(
        dispatcher_main.httpx,
        "AsyncClient",
        lambda: DummyAsyncClient(request_impl),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/auth/login", json={"username": "u", "password": "p"})

    assert response.status_code == 503
    assert "Service Unavailable" in response.json()["detail"]


async def test_malformed_bearer_header_returns_401_not_500():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products/list", headers={"Authorization": "Bearer"})

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


async def test_products_forwarding_strips_host_and_preserves_body_and_custom_headers(monkeypatch):
    captured = {}

    async def request_impl(method, url, headers=None, content=None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["content"] = content
        return DummyResponse(200, payload={"ok": True})

    monkeypatch.setattr(dispatcher_main, "is_authorized", lambda request: True)
    monkeypatch.setattr(
        dispatcher_main.httpx,
        "AsyncClient",
        lambda: DummyAsyncClient(request_impl),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch(
            "/products/item-1",
            headers={"X-Trace-Id": "trace-123", "Host": "evil.example"},
            json={"quantity": 2},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["method"] == "PATCH"
    assert captured["url"].endswith("/products/item-1")
    assert captured["headers"].get("x-trace-id") == "trace-123"
    assert "host" not in {k.lower(): v for k, v in captured["headers"].items()}
    assert json.loads(captured["content"]) == {"quantity": 2}

    