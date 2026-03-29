import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import orders as orders_router


pytestmark = pytest.mark.asyncio(loop_scope="function")


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length):
        return self._docs[:length]


class FakeResult:
    def __init__(self, inserted_id=None, matched_count=0, deleted_count=0):
        self.inserted_id = inserted_id
        self.matched_count = matched_count
        self.deleted_count = deleted_count


class FakeOrdersCollection:
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


@pytest.fixture(autouse=True)
def setup_fake_db():
    fake_db = FakeOrdersCollection()
    orders_router.orders_collection = fake_db
    return fake_db


async def test_get_orders_returns_200_and_empty_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/orders")

    assert response.status_code == 200
    assert response.json() == []


async def test_create_order_returns_201_and_computed_total_amount():
    payload = {
        "customer_id": "customer-001",
        "items": [
            {"product_id": "p1", "quantity": 2, "unit_price": 10.0},
            {"product_id": "p2", "quantity": 1, "unit_price": 5.5},
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/orders", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["customer_id"] == "customer-001"
    assert body["status"] == "pending"
    assert body["total_amount"] == 25.5


async def test_get_order_by_id_returns_200():
    payload = {
        "customer_id": "customer-002",
        "items": [{"product_id": "p7", "quantity": 1, "unit_price": 12.0}],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post("/orders", json=payload)
        order_id = create.json()["id"]
        get_response = await ac.get(f"/orders/{order_id}")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == order_id


async def test_get_order_missing_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/orders/66f2aa4f8ad9ad0d98da1111")

    assert response.status_code == 404


async def test_patch_order_returns_200_and_recomputes_total_amount():
    payload = {
        "customer_id": "customer-003",
        "items": [{"product_id": "p1", "quantity": 1, "unit_price": 9.0}],
    }
    patch_payload = {
        "items": [{"product_id": "p1", "quantity": 3, "unit_price": 7.5}],
        "status": "confirmed",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post("/orders", json=payload)
        order_id = create.json()["id"]
        patch_response = await ac.patch(f"/orders/{order_id}", json=patch_payload)

    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "confirmed"
    assert patch_response.json()["total_amount"] == 22.5


async def test_patch_order_missing_returns_404():
    patch_payload = {
        "status": "confirmed",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch("/orders/66f2aa4f8ad9ad0d98da1111", json=patch_payload)

    assert response.status_code == 404


async def test_delete_order_returns_204():
    payload = {
        "customer_id": "customer-004",
        "items": [{"product_id": "p9", "quantity": 2, "unit_price": 4.0}],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post("/orders", json=payload)
        order_id = create.json()["id"]
        delete_response = await ac.delete(f"/orders/{order_id}")
        get_after_delete = await ac.get(f"/orders/{order_id}")

    assert delete_response.status_code == 204
    assert get_after_delete.status_code == 404


async def test_delete_order_missing_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/orders/66f2aa4f8ad9ad0d98da1111")

    assert response.status_code == 404