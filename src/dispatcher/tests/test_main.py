import pytest 
import json
import httpx
from jose import jwt
from urllib.parse import urlsplit
from httpx import ASGITransport,AsyncClient
from fastapi import FastAPI, HTTPException
from app.main import app
import app.main as dispatcher_main
from app.core.security import SECRET_KEY, ALGORITHM

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


class DummyResponse:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class DummyAsyncClient:
    def __init__(self, request_impl):
        self._request_impl = request_impl

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, headers=None, content=None):
        return await self._request_impl(method, url, headers=headers, content=content)


async def test_auth_forwarding_passes_upstream_status_and_json(monkeypatch):
    async def request_impl(method, url, headers=None, content=None):
        assert method == "POST"
        assert url.endswith("/login")
        return DummyResponse(422, payload={"detail": "bad payload"})

    monkeypatch.setattr(
        dispatcher_main.httpx,
        "AsyncClient",
        lambda: DummyAsyncClient(request_impl),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/auth/login", json={"username": "u", "password": "p"})

    assert response.status_code == 422
    assert response.json() == {"detail": "bad payload"}


async def test_auth_forwarding_returns_503_when_upstream_unreachable(monkeypatch):
    async def request_impl(method, url, headers=None, content=None):
        raise httpx.RequestError("service down")

    monkeypatch.setattr(
        dispatcher_main.httpx,
        "AsyncClient",
        lambda: DummyAsyncClient(request_impl),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/auth/login", json={"username": "u", "password": "p"})

    assert response.status_code == 503
    assert "Service Unavailable" in response.json()["detail"]


async def test_malformed_bearer_header_returns_401_not_500():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products/list", headers={"Authorization": "Bearer"})

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


async def test_products_forwarding_strips_host_and_preserves_body_and_custom_headers(monkeypatch):
    captured = {}

    async def request_impl(method, url, headers=None, content=None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["content"] = content
        return DummyResponse(200, payload={"ok": True})

    monkeypatch.setattr(dispatcher_main, "is_authorized", lambda request: True)
    monkeypatch.setattr(
        dispatcher_main.httpx,
        "AsyncClient",
        lambda: DummyAsyncClient(request_impl),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch(
            "/products/item-1",
            headers={"X-Trace-Id": "trace-123", "Host": "evil.example"},
            json={"quantity": 2},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["method"] == "PATCH"
    assert captured["url"].endswith("/products/item-1")
    assert captured["headers"].get("x-trace-id") == "trace-123"
    assert "host" not in {k.lower(): v for k, v in captured["headers"].items()}
    assert json.loads(captured["content"]) == {"quantity": 2}


class MultiServiceAsyncClient:
    def __init__(self, routes: dict[str, object]):
        self._routes = routes

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, headers=None, content=None):
        parts = urlsplit(url)
        service = self._routes.get(parts.netloc)
        if not service:
            raise httpx.RequestError(f"Unknown upstream host: {parts.netloc}")

        path = parts.path or "/"
        transport = ASGITransport(app=service)
        async with AsyncClient(transport=transport, base_url=f"http://{parts.netloc}") as client:
            return await client.request(
                method,
                path,
                headers=headers,
                content=content,
            )


@pytest.fixture
def product_order_gateway_setup(monkeypatch):
    product_app = FastAPI()
    order_app = FastAPI()
    product_store = {}
    order_store = {}

    @product_app.get("/products")
    async def list_products():
        return list(product_store.values())

    @product_app.post("/products", status_code=201)
    async def create_product(payload: dict):
        product_id = str(len(product_store) + 1)
        doc = {"id": product_id, **payload}
        product_store[product_id] = doc
        return doc

    @product_app.get("/products/{product_id}")
    async def get_product(product_id: str):
        if product_id not in product_store:
            raise HTTPException(status_code=404, detail="Product not found")
        return product_store[product_id]

    @product_app.put("/products/{product_id}")
    async def put_product(product_id: str, payload: dict):
        if product_id not in product_store:
            raise HTTPException(status_code=404, detail="Product not found")
        product_store[product_id] = {"id": product_id, **payload}
        return product_store[product_id]

    @product_app.patch("/products/{product_id}")
    async def patch_product(product_id: str, payload: dict):
        if product_id not in product_store:
            raise HTTPException(status_code=404, detail="Product not found")
        product_store[product_id].update(payload)
        return product_store[product_id]

    @product_app.delete("/products/{product_id}", status_code=204)
    async def delete_product(product_id: str):
        if product_id not in product_store:
            raise HTTPException(status_code=404, detail="Product not found")
        del product_store[product_id]

    @order_app.get("/orders")
    async def list_orders():
        return list(order_store.values())

    @order_app.post("/orders", status_code=201)
    async def create_order(payload: dict):
        order_id = str(len(order_store) + 1)
        items = payload.get("items", [])
        total_amount = sum(item["quantity"] * item["unit_price"] for item in items)
        doc = {"id": order_id, **payload, "total_amount": float(total_amount)}
        order_store[order_id] = doc
        return doc

    @order_app.get("/orders/{order_id}")
    async def get_order(order_id: str):
        if order_id not in order_store:
            raise HTTPException(status_code=404, detail="Order not found")
        return order_store[order_id]

    @order_app.put("/orders/{order_id}")
    async def put_order(order_id: str, payload: dict):
        if order_id not in order_store:
            raise HTTPException(status_code=404, detail="Order not found")
        items = payload.get("items", [])
        total_amount = sum(item["quantity"] * item["unit_price"] for item in items)
        order_store[order_id] = {
            "id": order_id,
            **payload,
            "total_amount": float(total_amount),
        }
        return order_store[order_id]

    @order_app.patch("/orders/{order_id}")
    async def patch_order(order_id: str, payload: dict):
        if order_id not in order_store:
            raise HTTPException(status_code=404, detail="Order not found")
        order_store[order_id].update(payload)
        return order_store[order_id]

    @order_app.delete("/orders/{order_id}", status_code=204)
    async def delete_order(order_id: str):
        if order_id not in order_store:
            raise HTTPException(status_code=404, detail="Order not found")
        del order_store[order_id]

    monkeypatch.setattr(dispatcher_main, "is_authorized", lambda request: True)
    monkeypatch.setattr(
        dispatcher_main.httpx,
        "AsyncClient",
        lambda: MultiServiceAsyncClient(
            {
                "localhost:8001": product_app,
                "localhost:8002": order_app,
            }
        ),
    )


async def test_gateway_product_crud_flow(product_order_gateway_setup):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post(
            "/products",
            json={
                "name": "Desk Lamp",
                "description": "Warm light",
                "price": 40.0,
                "stock": 8,
            },
        )
        assert create.status_code == 201
        product_id = create.json()["id"]

        get_one = await ac.get(f"/products/{product_id}")
        list_all = await ac.get("/products")
        put_one = await ac.put(
            f"/products/{product_id}",
            json={
                "name": "Desk Lamp Plus",
                "description": "Warm light v2",
                "price": 55.0,
                "stock": 6,
            },
        )
        patch_one = await ac.patch(f"/products/{product_id}", json={"stock": 5})
        delete_one = await ac.delete(f"/products/{product_id}")
        missing = await ac.get(f"/products/{product_id}")

    assert get_one.status_code == 200
    assert list_all.status_code == 200
    assert len(list_all.json()) == 1
    assert put_one.status_code == 200
    assert put_one.json()["name"] == "Desk Lamp Plus"
    assert patch_one.status_code == 200
    assert patch_one.json()["stock"] == 5
    assert delete_one.status_code == 204
    assert missing.status_code == 404


async def test_gateway_order_crud_flow(product_order_gateway_setup):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post(
            "/orders",
            json={
                "customer_id": "u-100",
                "items": [{"product_id": "p-10", "quantity": 2, "unit_price": 12.5}],
                "status": "created",
            },
        )
        assert create.status_code == 201
        order_id = create.json()["id"]

        get_one = await ac.get(f"/orders/{order_id}")
        list_all = await ac.get("/orders")
        put_one = await ac.put(
            f"/orders/{order_id}",
            json={
                "customer_id": "u-100",
                "items": [{"product_id": "p-10", "quantity": 3, "unit_price": 12.5}],
                "status": "processing",
            },
        )
        patch_one = await ac.patch(f"/orders/{order_id}", json={"status": "completed"})
        delete_one = await ac.delete(f"/orders/{order_id}")
        missing = await ac.get(f"/orders/{order_id}")

    assert get_one.status_code == 200
    assert list_all.status_code == 200
    assert len(list_all.json()) == 1
    assert put_one.status_code == 200
    assert put_one.json()["total_amount"] == 37.5
    assert patch_one.status_code == 200
    assert patch_one.json()["status"] == "completed"
    assert delete_one.status_code == 204
    assert missing.status_code == 404


async def test_user_named_admin_without_profile_cannot_write_products(monkeypatch):
    captured = []

    async def request_impl(method, url, headers=None, content=None):
        captured.append((method, url))
        return DummyResponse(200, payload={"ok": True})

    monkeypatch.setattr(
        dispatcher_main.httpx,
        "AsyncClient",
        lambda: DummyAsyncClient(request_impl),
    )

    token = jwt.encode({"sub": "admin"}, SECRET_KEY, algorithm=ALGORITHM)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/products",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Unsafe", "price": 10.0, "stock": 1},
        )

    assert response.status_code == 403
    assert len(captured) == 0


async def test_bootstrap_profile_allows_products_get_but_blocks_products_post(monkeypatch):
    captured = []

    async def request_impl(method, url, headers=None, content=None):
        captured.append((method, url))
        return DummyResponse(200, payload={"ok": True})

    monkeypatch.setenv(
        "DISPATCHER_ACCESS_PROFILES_JSON",
        json.dumps(
            [
                {
                    "username": "bootstrap-user",
                    "roles": ["order_reader"],
                    "service_permissions": {"products": ["GET"]},
                }
            ]
        ),
    )
    monkeypatch.setattr(
        dispatcher_main.httpx,
        "AsyncClient",
        lambda: DummyAsyncClient(request_impl),
    )

    token = jwt.encode({"sub": "bootstrap-user", "roles": []}, SECRET_KEY, algorithm=ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        products_get = await ac.get("/products/list", headers=headers)
        products_post = await ac.post(
            "/products",
            headers=headers,
            json={"name": "Blocked", "price": 11.0, "stock": 1},
        )

    assert products_get.status_code == 200
    assert products_post.status_code == 403
    assert len(captured) == 1

    