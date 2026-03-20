import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

pytestmark = pytest.mark.asyncio(loop_scope="function")


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

    