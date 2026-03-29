import pytest
import httpx
from datetime import datetime, timedelta, timezone
from httpx import ASGITransport, AsyncClient
from jose import jwt
from fastapi import Request
from app.main import app

pytestmark = pytest.mark.asyncio(loop_scope="function")
SECRET_KEY = "yazlab-secret-key"


def _valid_token() -> str:
    payload = {
        "sub": "dispatcher-user",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


@pytest.mark.parametrize("path", ["/products", "/orders"])
async def test_missing_token_returns_401_for_protected_routes(path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(path)
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


@pytest.mark.parametrize("path", ["/products", "/orders"])
async def test_malformed_bearer_header_returns_401(path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(path, headers={"Authorization": "Token abc123"})
    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/products", "/orders"])
async def test_invalid_token_returns_401(path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(path, headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "method,path",
    [
        ("put", "/products"),
        ("put", "/orders"),
    ],
)
async def test_valid_token_but_forbidden_method_returns_403(method, path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        request_fn = getattr(ac, method)
        response = await request_fn(path, headers={"Authorization": f"Bearer {_valid_token()}"})
    assert response.status_code == 403
    assert response.json() == {"error": "Forbidden"}


@pytest.mark.asyncio(loop_scope="function")
async def test_auth_proxy_passthroughs_upstream_status_and_body(monkeypatch):
    async def fake_forward_auth_request(request, path):
        return 422, {"detail": "invalid credentials"}
    
    import app.main as dispatcher_mod
    monkeypatch.setattr(dispatcher_mod, "forward_auth_request", fake_forward_auth_request)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/auth/login", json={"username": "u", "password": "p"})

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid credentials"}

@pytest.mark.asyncio(loop_scope="function")
async def test_auth_proxy_returns_503_when_upstream_unreachable(monkeypatch):
    async def fake_forward_auth_request(request, path):
        raise RuntimeError("Service down")

    import app.main as dispatcher_mod
    monkeypatch.setattr(dispatcher_mod, "forward_auth_request", fake_forward_auth_request)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/auth/login", json={"username": "u", "password": "p"})

    assert response.status_code == 503
    assert response.json() == {"error": "Service Unavailable"}

@pytest.mark.asyncio(loop_scope="function")
async def test_products_route_is_forwarded(monkeypatch):
    async def fake_forward(request, base_url, path):
        # Dispatcher doğru servise yönlendiriyor mu?
        assert base_url.endswith("product_service:8000")
        assert path == "products"
        return 200, {"message": "product ok"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/products", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"message": "product ok"}

@pytest.mark.asyncio(loop_scope="function")
async def test_orders_route_is_forwarded(monkeypatch):
    async def fake_forward(request, base_url, path):
        assert base_url.endswith("order_service:8000")
        assert path == "orders"
        return 200, {"message": "order ok"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers= {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/orders", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"message": "order ok"}


@pytest.mark.asyncio(loop_scope="function")
async def test_order_detail_get_route_is_forwarded(monkeypatch):
    async def fake_forward(request, base_url, path):
        assert base_url.endswith("order_service:8000")
        assert path == "orders/abc123"
        return 200, {"id": "abc123", "status": "pending"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/orders/abc123", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"id": "abc123", "status": "pending"}


@pytest.mark.asyncio(loop_scope="function")
async def test_order_detail_patch_route_is_forwarded(monkeypatch):
    async def fake_forward(request, base_url, path):
        assert base_url.endswith("order_service:8000")
        assert path == "orders/abc123"
        body = await request.json()
        assert body == {"status": "confirmed"}
        return 200, {"id": "abc123", "status": "confirmed"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.patch("/orders/abc123", json={"status": "confirmed"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


@pytest.mark.asyncio(loop_scope="function")
async def test_order_detail_delete_route_returns_204(monkeypatch):
    async def fake_forward(request, base_url, path):
        assert base_url.endswith("order_service:8000")
        assert path == "orders/abc123"
        return 204, None

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.delete("/orders/abc123", headers=headers)

    assert response.status_code == 204


@pytest.mark.asyncio(loop_scope="function")
async def test_order_detail_404_is_preserved(monkeypatch):
    async def fake_forward(request, base_url, path):
        return 404, {"detail": "Order not found"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/orders/abc123", headers=headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


@pytest.mark.asyncio(loop_scope="function")
async def test_order_upstream_connection_error_returns_503(monkeypatch):
    async def fake_forward(request, base_url, path):
        raise httpx.ConnectError("upstream down")

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/orders", headers=headers)

    assert response.status_code == 503
    assert response.json() == {"error": "Service Unavailable"}

@pytest.mark.asyncio(loop_scope="function")
async def test_unknown_route_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/unknown")

    assert response.status_code == 404

@pytest.mark.asyncio(loop_scope="function")
async def test_body_passthrough(monkeypatch):
    async def fake_forward(request, base_url, path):
        body = await request.json()
        assert body == {"name": "test-product"}
        return 200, {"ok": True}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.post("/products", json={"name": "test-product"}, headers=headers)
    assert response.status_code == 200
