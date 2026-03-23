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
