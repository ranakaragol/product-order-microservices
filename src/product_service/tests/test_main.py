import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import products as products_router

pytestmark = pytest.mark.asyncio(loop_scope="function")


class FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    async def to_list(self, length: int):
        return self._docs[:length]


class FakeResult:
    def __init__(self, inserted_id=None, matched_count=0, deleted_count=0):
        self.inserted_id = inserted_id
        self.matched_count = matched_count
        self.deleted_count = deleted_count


class FakeProductsCollection:
    def __init__(self):
        self._docs = {}

    def find(self, _query):
        return FakeCursor(list(self._docs.values()))

    async def find_one(self, query):
        return self._docs.get(query.get("_id"))

    async def insert_one(self, payload):
        inserted_id = ObjectId()
        self._docs[inserted_id] = {"_id": inserted_id, **payload}
        return FakeResult(inserted_id=inserted_id)


@pytest.fixture
def fake_collection():
    collection = FakeProductsCollection()
    products_router.products_collection = collection
    return collection


async def test_get_products_returns_200_and_empty_list(fake_collection):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products")

    assert response.status_code == 200
    assert response.json() == []


async def test_post_products_returns_201_and_created_product(fake_collection):
    payload = {
        "name": "Keyboard",
        "description": "Mechanical",
        "price": 99.9,
        "stock": 15,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/products", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["name"] == "Keyboard"


async def test_get_product_by_id_returns_200(fake_collection):
    payload = {
        "name": "Monitor",
        "description": "4K",
        "price": 300.0,
        "stock": 7,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_response = await ac.post("/products", json=payload)
        product_id = create_response.json()["id"]
        get_response = await ac.get(f"/products/{product_id}")

    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Monitor"


async def test_get_product_by_id_returns_404_when_missing(fake_collection):
    missing_id = "66f2aa4f8ad9ad0d98da1111"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/products/{missing_id}")

    assert response.status_code == 404
