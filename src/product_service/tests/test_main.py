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

    async def update_one(self, query, update):
        object_id = query.get("_id")
        if object_id not in self._docs:
            return FakeResult(matched_count=0)

        self._docs[object_id].update(update.get("$set", {}))
        return FakeResult(matched_count=1)


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


async def test_put_and_patch_product_return_200(fake_collection):
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

    assert put_response.status_code == 200
    assert put_response.json()["name"] == "Mouse Pro"
    assert patch_response.status_code == 200
    assert patch_response.json()["stock"] == 20


@pytest.mark.parametrize(
    "method,path,payload",
    [
        (
            "put",
            "/products/66f2aa4f8ad9ad0d98da1111",
            {"name": "X", "description": None, "price": 1.0, "stock": 1},
        ),
        ("patch", "/products/66f2aa4f8ad9ad0d98da1111", {"stock": 1}),
    ],
)
async def test_put_patch_return_404_when_missing(fake_collection, method, path, payload):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await getattr(ac, method)(path, json=payload)

    assert response.status_code == 404
