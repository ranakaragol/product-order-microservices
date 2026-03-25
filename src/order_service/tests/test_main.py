import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.mark.asyncio(loop_scope="function")
async def test_get_orders_returns_200_and_empty_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response=await ac.get("/orders")

    assert response.status_code==200
    assert response.json()==[]

@pytest.mark.asyncio(loop_scope="function")
async def test_create_order():
    payload={
        "product_id": "123",
        "quantity": 2

    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response=await ac.post("/orders", json=payload)

    assert response.status_code==201
    assert response.json()["product_id"]== "123"

@pytest.mark.asyncio(loop_scope="function")
async def test_get_order_by_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create=await ac.post("/orders", json={
            "product_id": "123",
            "quantity": 1
        })

        order_id=create.json()["id"]
        get_res=await ac.get(f"/orders/{order_id}")

    assert get_res.status_code==200


@pytest.mark.asyncio(loop_scope="function")
async def test_get_order_invalid_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response=await ac.get("/orders/invalid_id")

    assert response.status_code==200

