import pytest 
from httpx import ASGITransport,AsyncClient
from app.main import app

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

    