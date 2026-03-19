import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_get_products_returns_empty_list_initially():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products")

    assert response.status_code == 200
    assert response.json() == []
