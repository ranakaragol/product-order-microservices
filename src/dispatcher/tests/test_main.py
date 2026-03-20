import pytest
from datetime import datetime, timedelta, timezone
from httpx import ASGITransport, AsyncClient
from jose import jwt
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
        ("post", "/products"),
        ("delete", "/orders"),
    ],
)
async def test_valid_token_but_forbidden_method_returns_403(method, path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        request_fn = getattr(ac, method)
        response = await request_fn(path, headers={"Authorization": f"Bearer {_valid_token()}"})
    assert response.status_code == 403
    assert response.json() == {"error": "Forbidden"}

    