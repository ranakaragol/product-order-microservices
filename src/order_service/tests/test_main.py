import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response
from app.main import app
from app.routers import orders as orders_router
from bson import ObjectId

class FakeCursor:
    def __init__(self, docs):
        self._docs = docs
    async def to_list(self, length):
        return self._docs[:length]

class FakeOrdersCollection:
    def __init__(self):
        self._docs = {}
    def find(self, query):
        return FakeCursor(list(self._docs.values()))
    async def find_one(self, query):
        return self._docs.get(query.get("_id"))
    async def insert_one(self, payload):
        inserted_id = ObjectId()
        self._docs[inserted_id] = {"_id": inserted_id, **payload}
        class Result: inserted_id = None
        res = Result(); res.inserted_id = inserted_id
        return res

@pytest.fixture(autouse=True)
def setup_fake_db():
    fake_db = FakeOrdersCollection()
    orders_router.orders_collection = fake_db
    yield

# --- Testler ---

@pytest.mark.asyncio(loop_scope="function")
async def test_get_orders_returns_200_and_empty_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/orders")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio(loop_scope="function")
@respx.mock
async def test_create_order(respx_mock):
    # Ürün servisini "Stok Var" (200 OK) olarak taklit ediyoruz
    respx_mock.get(url__regex=r".*/products/123").mock(
        return_value=Response(200, json={"id": "123", "stock": 100})
    )
    
    payload = {"product_id": "123", "quantity": 2}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/orders", json=payload)
    
    assert response.status_code == 201
    assert response.json()["product_id"] == "123"

@pytest.mark.asyncio(loop_scope="function")
@respx.mock
async def test_get_order_by_id(respx_mock):
    # Sipariş oluşturabilmek için önce stok onayını taklit et
    respx_mock.get(url__regex=r".*/products/123").mock(
        return_value=Response(200, json={"id": "123", "stock": 100})
    )
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post("/orders", json={"product_id": "123", "quantity": 1})
        order_id = create.json()["id"]
        get_res = await ac.get(f"/orders/{order_id}")
    
    assert get_res.status_code == 200
    assert get_res.json()["id"] == order_id

@pytest.mark.asyncio(loop_scope="function")
async def test_get_order_invalid_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Geçersiz bir MongoDB ObjectId'si formatında rastgele bir ID
        response = await ac.get("/orders/66f2aa4f8ad9ad0d98da1111")
    assert response.status_code == 404

@pytest.mark.asyncio(loop_scope="function")
@respx.mock
async def test_create_order_insufficient_stock_returns_400(respx_mock):
    # Ürün servisini "Ürün Yok" veya "Hata" (404) olarak taklit ediyoruz
    respx_mock.get(url__regex=r".*/products/.*").mock(return_value=Response(404))
    
    payload = {"product_id": "non_existent_product", "quantity": 9999}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/orders", json=payload)
    
    assert response.status_code == 400
    # Sözdizimi hatasını düzelttik: response.json()["detail"]
    assert response.json()["detail"] == "Insufficient stock or product not found"