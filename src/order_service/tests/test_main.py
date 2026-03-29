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