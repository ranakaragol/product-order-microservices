import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.routers import products as products_router


pytestmark = pytest.mark.asyncio(loop_scope="function")


class FakeCursor:
    def __init__(self, docs):
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

    async def update_one(self, query, update):
        object_id = query.get("_id")
        if object_id not in self._docs:
            return FakeResult(matched_count=0)

        self._docs[object_id].update(update.get("$set", {}))
        return FakeResult(matched_count=1)

    async def delete_one(self, query):
        object_id = query.get("_id")
        if object_id in self._docs:
            del self._docs[object_id]
            return FakeResult(deleted_count=1)
        return FakeResult(deleted_count=0)


@pytest.fixture
def fake_collection():
    collection = FakeProductsCollection()
    products_router.products_collection = collection
    return collection


async def test_get_products_returns_empty_list_initially(fake_collection):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products")

    assert response.status_code == 200
    assert response.json() == []


async def test_create_and_get_product(fake_collection):
    payload = {
        "name": "Keyboard",
        "description": "Mechanical",
        "price": 99.9,
        "stock": 15,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_response = await ac.post("/products", json=payload)

        assert create_response.status_code == 201
        created = create_response.json()

        get_response = await ac.get(f"/products/{created['id']}")

    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Keyboard"


async def test_put_patch_and_delete_product(fake_collection):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_response = await ac.post(
            "/products",
            json={
                "name": "Mouse",
                "description": "Wireless",
                "price": 25.0,
                "stock": 50,
            },
        )
        product_id = create_response.json()["id"]

        put_response = await ac.put(
            f"/products/{product_id}",
            json={
                "name": "Mouse Pro",
                "description": "Wireless Pro",
                "price": 35.0,
                "stock": 30,
            },
        )
        patch_response = await ac.patch(f"/products/{product_id}", json={"stock": 20})
        delete_response = await ac.delete(f"/products/{product_id}")
        get_after_delete = await ac.get(f"/products/{product_id}")

    assert put_response.status_code == 200
    assert put_response.json()["name"] == "Mouse Pro"
    assert patch_response.status_code == 200
    assert patch_response.json()["stock"] == 20
    assert delete_response.status_code == 204
    assert get_after_delete.status_code == 404
