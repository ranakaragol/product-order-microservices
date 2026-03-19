import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import orders as orders_router

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


@pytest.fixture
def fake_collection():
    collection = FakeOrdersCollection()
    orders_router.orders_collection = collection
    return collection


async def test_get_orders_returns_empty_list_initially(fake_collection):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/orders")

    assert response.status_code == 200
    assert response.json() == []


async def test_create_and_get_order(fake_collection):
    payload = {
        "customer_id": "user-1",
        "items": [
            {"product_id": "p-1", "quantity": 2, "unit_price": 10.0},
            {"product_id": "p-2", "quantity": 1, "unit_price": 15.0},
        ],
        "status": "created",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_response = await ac.post("/orders", json=payload)
        assert create_response.status_code == 201
        created = create_response.json()

        get_response = await ac.get(f"/orders/{created['id']}")

    assert get_response.status_code == 200
    assert get_response.json()["total_amount"] == 35.0


async def test_put_patch_and_delete_order(fake_collection):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_response = await ac.post(
            "/orders",
            json={
                "customer_id": "user-2",
                "items": [{"product_id": "p-3", "quantity": 3, "unit_price": 5.0}],
                "status": "created",
            },
        )
        order_id = create_response.json()["id"]

        put_response = await ac.put(
            f"/orders/{order_id}",
            json={
                "customer_id": "user-2",
                "items": [{"product_id": "p-3", "quantity": 4, "unit_price": 5.0}],
                "status": "processing",
            },
        )

        patch_response = await ac.patch(f"/orders/{order_id}", json={"status": "completed"})
        delete_response = await ac.delete(f"/orders/{order_id}")
        get_after_delete = await ac.get(f"/orders/{order_id}")

    assert put_response.status_code == 200
    assert put_response.json()["total_amount"] == 20.0
    assert put_response.json()["status"] == "processing"
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "completed"
    assert delete_response.status_code == 204
    assert get_after_delete.status_code == 404
