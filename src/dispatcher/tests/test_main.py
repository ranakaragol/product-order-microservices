import pytest
import httpx
import importlib
import sys
from datetime import datetime, timedelta, timezone
from httpx import ASGITransport, AsyncClient
from jose import jwt
from fastapi import Request
from pathlib import Path
from app.main import app

pytestmark = pytest.mark.asyncio(loop_scope="function")
SECRET_KEY = "yazlab-secret-key"
DEFAULT_AUTHENTICATED_SUBJECT = "default-authenticated"


def _valid_token() -> str:
    payload = {
        "sub": "dispatcher-user",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


class FakeAccessProfileRepository:
    def __init__(self, profiles_by_subject=None):
        self._profiles_by_subject = profiles_by_subject or {}

    async def get_profile_by_subject(self, subject: str):
        profile = self._profiles_by_subject.get(subject)
        if profile is not None:
            return profile

        return self._profiles_by_subject.get(DEFAULT_AUTHENTICATED_SUBJECT)


class FakeLogsCollection:
    def __init__(self):
        self.entries = []

    async def insert_one(self, document):
        self.entries.append(document)
        return {"acknowledged": True}


class FakeAuthUsersCollection:
    def __init__(self):
        self._users = {}

    async def find_one(self, query):
        return self._users.get(query.get("username"))

    async def insert_one(self, document):
        self._users[document["username"]] = dict(document)
        return {"inserted_id": document["username"]}


class FakeSeedRepository:
    def __init__(self):
        self.seed_calls = 0

    async def seed_bootstrap_profiles(self):
        self.seed_calls += 1


def _install_access_profiles(monkeypatch, profiles_by_subject=None):
    import app.core.security as security_mod

    repository = FakeAccessProfileRepository(profiles_by_subject=profiles_by_subject)
    monkeypatch.setattr(security_mod, "get_access_profile_repository", lambda: repository)
    return repository


def _install_log_capture(monkeypatch):
    import app.main as dispatcher_mod

    fake_logs = FakeLogsCollection()
    monkeypatch.setattr(dispatcher_mod, "logs_collection", fake_logs)
    return fake_logs


def _load_auth_app_modules():
    auth_service_root = Path(__file__).resolve().parents[2] / "auth_service"
    dispatcher_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }

    for module_name in list(dispatcher_modules):
        sys.modules.pop(module_name, None)

    sys.path.insert(0, str(auth_service_root))
    try:
        auth_main = importlib.import_module("app.main")
        auth_router = importlib.import_module("app.routers.auth")
        return auth_main.app, auth_router
    finally:
        sys.path.remove(str(auth_service_root))
        for module_name in list(sys.modules):
            if module_name == "app" or module_name.startswith("app."):
                sys.modules.pop(module_name, None)
        sys.modules.update(dispatcher_modules)


def _install_real_auth_service_harness(monkeypatch):
    auth_app, auth_router = _load_auth_app_modules()
    fake_users = FakeAuthUsersCollection()
    monkeypatch.setattr(auth_router, "users_collection", fake_users)

    async def fake_forward_auth_request(request, path):
        async with AsyncClient(
            transport=ASGITransport(app=auth_app),
            base_url="http://auth-service.test",
        ) as auth_client:
            upstream_response = await auth_client.request(
                method=request.method,
                url=f"/{path.lstrip('/')}",
                params=request.query_params,
                content=await request.body(),
                headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            )

        try:
            payload = upstream_response.json()
        except ValueError:
            payload = upstream_response.text

        return upstream_response.status_code, payload

    monkeypatch.setattr("app.main.forward_auth_request", fake_forward_auth_request)
    return fake_users


def _install_default_read_only_profile(monkeypatch):
    _install_access_profiles(
        monkeypatch,
        profiles_by_subject={
            DEFAULT_AUTHENTICATED_SUBJECT: {
                "subject": DEFAULT_AUTHENTICATED_SUBJECT,
                "permissions": [{"resource": "/products", "methods": ["GET"]}],
            }
        },
    )


def _install_dispatcher_user_full_access(monkeypatch):
    _install_access_profiles(
        monkeypatch,
        profiles_by_subject={
            "dispatcher-user": {
                "subject": "dispatcher-user",
                "permissions": [
                    {"resource": "/products", "methods": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                    {"resource": "/orders", "methods": ["GET", "POST", "PATCH", "DELETE"]},
                ],
            }
        },
    )


async def _register_and_login_through_dispatcher(ac: AsyncClient, username: str, password: str) -> str:
    register_response = await ac.post(
        "/auth/register",
        json={"username": username, "password": password},
    )
    assert register_response.status_code == 200

    login_response = await ac.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.json()["token"]


@pytest.mark.parametrize("path", ["/products", "/orders"])
async def test_missing_token_returns_401_for_protected_routes(path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(path)
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


@pytest.mark.parametrize("path", ["/products", "/orders"])
async def test_malformed_bearer_header_returns_401(path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(path, headers={"Authorization": "Token abc123"})
    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/products", "/orders"])
async def test_invalid_token_returns_401(path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(path, headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


@pytest.mark.asyncio(loop_scope="function")
async def test_valid_token_without_matching_access_profile_returns_403(monkeypatch):
    _install_access_profiles(monkeypatch, profiles_by_subject={})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products", headers={"Authorization": f"Bearer {_valid_token()}"})

    assert response.status_code == 403
    assert response.json() == {"error": "Forbidden"}


@pytest.mark.asyncio(loop_scope="function")
async def test_valid_token_with_allowed_access_profile_can_access_product_and_order_routes(monkeypatch):
    _install_access_profiles(
        monkeypatch,
        profiles_by_subject={
            "dispatcher-user": {
                "subject": "dispatcher-user",
                "permissions": [
                    {"resource": "/products", "methods": ["GET"]},
                    {"resource": "/orders", "methods": ["PATCH"]},
                ],
            }
        },
    )

    async def fake_forward(request, base_url, path):
        if path == "products":
            return 200, [{"id": "p1"}]
        if path == "orders/abc123":
            return 200, {"id": "abc123", "status": "confirmed"}
        raise AssertionError(f"Unexpected forwarded path: {path}")

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        products_response = await ac.get("/products", headers=headers)
        orders_response = await ac.patch("/orders/abc123", json={"status": "confirmed"}, headers=headers)

    assert products_response.status_code == 200
    assert products_response.json() == [{"id": "p1"}]
    assert orders_response.status_code == 200
    assert orders_response.json() == {"id": "abc123", "status": "confirmed"}


async def test_valid_token_but_forbidden_order_method_returns_403(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/orders", headers={"Authorization": f"Bearer {_valid_token()}"})
    assert response.status_code == 403
    assert response.json() == {"error": "Forbidden"}


async def test_valid_token_but_unsupported_product_collection_method_returns_405(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/products", headers={"Authorization": f"Bearer {_valid_token()}"})
    assert response.status_code == 405


@pytest.mark.asyncio(loop_scope="function")
async def test_auth_proxy_passthroughs_upstream_status_and_body(monkeypatch):
    async def fake_forward_auth_request(request, path):
        return 422, {"detail": "invalid credentials"}
    
    import app.main as dispatcher_mod
    monkeypatch.setattr(dispatcher_mod, "forward_auth_request", fake_forward_auth_request)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/auth/login", json={"username": "u", "password": "p"})

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid credentials"}

@pytest.mark.asyncio(loop_scope="function")
async def test_auth_proxy_returns_503_when_httpx_upstream_is_unreachable(monkeypatch):
    async def fake_forward_auth_request(request, path):
        raise httpx.ConnectError("Service down")

    import app.main as dispatcher_mod
    monkeypatch.setattr(dispatcher_mod, "forward_auth_request", fake_forward_auth_request)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/auth/login", json={"username": "u", "password": "p"})

    assert response.status_code == 503
    assert response.json() == {"error": "Service Unavailable"}


@pytest.mark.asyncio(loop_scope="function")
async def test_dispatcher_startup_seeds_access_profiles(monkeypatch):
    import app.main as dispatcher_mod

    fake_repository = FakeSeedRepository()
    monkeypatch.setattr(dispatcher_mod, "get_access_profile_repository", lambda: fake_repository)

    await dispatcher_mod.seed_dispatcher_access_profiles()

    assert fake_repository.seed_calls == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_real_auth_chain_allows_read_only_user_to_get_products(monkeypatch):
    _install_default_read_only_profile(monkeypatch)
    _install_real_auth_service_harness(monkeypatch)

    async def fake_forward(request, base_url, path):
        assert base_url.endswith("product_service:8000")
        assert path == "products"
        return 200, [{"id": "p-real-auth"}]

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _register_and_login_through_dispatcher(
            ac,
            username="real-auth-reader",
            password="reader-password",
        )
        products_response = await ac.get(
            "/products",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert products_response.status_code == 200
    assert products_response.json() == [{"id": "p-real-auth"}]


@pytest.mark.asyncio(loop_scope="function")
async def test_real_auth_chain_forbids_read_only_user_product_create(monkeypatch):
    _install_default_read_only_profile(monkeypatch)
    _install_real_auth_service_harness(monkeypatch)

    async def fake_forward(request, base_url, path):
        raise AssertionError("Forbidden write request must not be forwarded")

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _register_and_login_through_dispatcher(
            ac,
            username="real-auth-writer",
            password="writer-password",
        )
        create_response = await ac.post(
            "/products",
            json={"name": "Mouse", "description": None, "price": 10.0, "stock": 3},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert create_response.status_code == 403
    assert create_response.json() == {"error": "Forbidden"}


@pytest.mark.asyncio(loop_scope="function")
async def test_auth_verify_token_without_header_returns_401_via_real_auth_service(monkeypatch):
    _install_real_auth_service_harness(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/auth/verify-token")

    assert response.status_code == 401

@pytest.mark.asyncio(loop_scope="function")
async def test_products_route_is_forwarded(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        # Dispatcher doğru servise yönlendiriyor mu?
        assert base_url.endswith("product_service:8000")
        assert path == "products"
        return 200, {"message": "product ok"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/products", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"message": "product ok"}


@pytest.mark.asyncio(loop_scope="function")
async def test_product_detail_get_route_is_forwarded(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        assert base_url.endswith("product_service:8000")
        assert path == "products/abc123"
        return 200, {"id": "abc123", "name": "Keyboard"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/products/abc123", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"id": "abc123", "name": "Keyboard"}


@pytest.mark.asyncio(loop_scope="function")
async def test_product_create_route_forwards_body_and_preserves_201(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        assert base_url.endswith("product_service:8000")
        assert path == "products"
        assert await request.json() == {
            "name": "Keyboard",
            "description": "Mechanical",
            "price": 99.9,
            "stock": 12,
        }
        return 201, {"id": "p1", "name": "Keyboard"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    payload = {
        "name": "Keyboard",
        "description": "Mechanical",
        "price": 99.9,
        "stock": 12,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.post("/products", json=payload, headers=headers)

    assert response.status_code == 201
    assert response.json() == {"id": "p1", "name": "Keyboard"}


@pytest.mark.asyncio(loop_scope="function")
async def test_product_detail_put_route_is_forwarded(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        assert base_url.endswith("product_service:8000")
        assert path == "products/abc123"
        assert await request.json() == {
            "name": "Keyboard Pro",
            "description": "Hot swap",
            "price": 129.9,
            "stock": 10,
        }
        return 200, {"id": "abc123", "name": "Keyboard Pro"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    payload = {
        "name": "Keyboard Pro",
        "description": "Hot swap",
        "price": 129.9,
        "stock": 10,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.put("/products/abc123", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"id": "abc123", "name": "Keyboard Pro"}


@pytest.mark.asyncio(loop_scope="function")
async def test_product_detail_patch_route_is_forwarded(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        assert base_url.endswith("product_service:8000")
        assert path == "products/abc123"
        assert await request.json() == {"stock": 8}
        return 200, {"id": "abc123", "stock": 8}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.patch("/products/abc123", json={"stock": 8}, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"id": "abc123", "stock": 8}


@pytest.mark.asyncio(loop_scope="function")
async def test_product_detail_delete_route_returns_204(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        assert base_url.endswith("product_service:8000")
        assert path == "products/abc123"
        return 204, None

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.delete("/products/abc123", headers=headers)

    assert response.status_code == 204


@pytest.mark.asyncio(loop_scope="function")
async def test_product_detail_404_is_preserved(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        assert path == "products/missing-id"
        return 404, {"detail": "Product not found"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/products/missing-id", headers=headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}


@pytest.mark.asyncio(loop_scope="function")
async def test_product_upstream_connection_error_returns_503(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        raise httpx.ConnectError("upstream down")

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/products/abc123", headers=headers)

    assert response.status_code == 503
    assert response.json() == {"error": "Service Unavailable"}


@pytest.mark.asyncio(loop_scope="function")
async def test_product_detail_put_requires_authentication():
    payload = {
        "name": "Keyboard Pro",
        "description": "Hot swap",
        "price": 129.9,
        "stock": 10,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/products/abc123", json=payload)

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


@pytest.mark.asyncio(loop_scope="function")
async def test_product_detail_patch_rejects_invalid_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch(
            "/products/abc123",
            json={"stock": 8},
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


@pytest.mark.asyncio(loop_scope="function")
async def test_orders_route_is_forwarded(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        assert base_url.endswith("order_service:8000")
        assert path == "orders"
        return 200, {"message": "order ok"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers= {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/orders", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"message": "order ok"}


@pytest.mark.asyncio(loop_scope="function")
async def test_order_detail_get_route_is_forwarded(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        assert base_url.endswith("order_service:8000")
        assert path == "orders/abc123"
        return 200, {"id": "abc123", "status": "pending"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/orders/abc123", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"id": "abc123", "status": "pending"}


@pytest.mark.asyncio(loop_scope="function")
async def test_order_detail_patch_route_is_forwarded(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        assert base_url.endswith("order_service:8000")
        assert path == "orders/abc123"
        body = await request.json()
        assert body == {"status": "confirmed"}
        return 200, {"id": "abc123", "status": "confirmed"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.patch("/orders/abc123", json={"status": "confirmed"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


@pytest.mark.asyncio(loop_scope="function")
async def test_order_detail_delete_route_returns_204(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        assert base_url.endswith("order_service:8000")
        assert path == "orders/abc123"
        return 204, None

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.delete("/orders/abc123", headers=headers)

    assert response.status_code == 204


@pytest.mark.asyncio(loop_scope="function")
async def test_order_detail_404_is_preserved(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        return 404, {"detail": "Order not found"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/orders/abc123", headers=headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


@pytest.mark.asyncio(loop_scope="function")
async def test_order_upstream_connection_error_returns_503(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)

    async def fake_forward(request, base_url, path):
        raise httpx.ConnectError("upstream down")

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_valid_token()}"}
        response = await ac.get("/orders", headers=headers)

    assert response.status_code == 503
    assert response.json() == {"error": "Service Unavailable"}

@pytest.mark.asyncio(loop_scope="function")
async def test_unknown_route_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/unknown")

    assert response.status_code == 404


@pytest.mark.asyncio(loop_scope="function")
async def test_missing_token_denied_request_is_logged(monkeypatch):
    fake_logs = _install_log_capture(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products")

    assert response.status_code == 401
    assert len(fake_logs.entries) == 1
    assert fake_logs.entries[0]["path"] == "/products"
    assert fake_logs.entries[0]["status_code"] == 401


@pytest.mark.asyncio(loop_scope="function")
async def test_invalid_token_denied_request_is_logged(monkeypatch):
    fake_logs = _install_log_capture(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert len(fake_logs.entries) == 1
    assert fake_logs.entries[0]["path"] == "/products"
    assert fake_logs.entries[0]["status_code"] == 401


@pytest.mark.asyncio(loop_scope="function")
async def test_forbidden_request_is_logged(monkeypatch):
    _install_access_profiles(monkeypatch, profiles_by_subject={})
    fake_logs = _install_log_capture(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products", headers={"Authorization": f"Bearer {_valid_token()}"})

    assert response.status_code == 403
    assert len(fake_logs.entries) == 1
    assert fake_logs.entries[0]["path"] == "/products"
    assert fake_logs.entries[0]["status_code"] == 403


@pytest.mark.asyncio(loop_scope="function")
async def test_allowed_request_is_logged(monkeypatch):
    _install_access_profiles(
        monkeypatch,
        profiles_by_subject={
            "dispatcher-user": {
                "subject": "dispatcher-user",
                "permissions": [{"resource": "/products", "methods": ["GET"]}],
            }
        },
    )
    fake_logs = _install_log_capture(monkeypatch)

    async def fake_forward(request, base_url, path):
        return 200, [{"id": "p1"}]

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products", headers={"Authorization": f"Bearer {_valid_token()}"})

    assert response.status_code == 200
    assert len(fake_logs.entries) == 1
    assert fake_logs.entries[0]["status_code"] == 200


@pytest.mark.asyncio(loop_scope="function")
async def test_upstream_unavailable_request_is_logged(monkeypatch):
    _install_dispatcher_user_full_access(monkeypatch)
    fake_logs = _install_log_capture(monkeypatch)

    async def fake_forward(request, base_url, path):
        raise httpx.ConnectError("upstream down")

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products", headers={"Authorization": f"Bearer {_valid_token()}"})

    assert response.status_code == 503
    assert len(fake_logs.entries) == 1
    assert fake_logs.entries[0]["path"] == "/products"
    assert fake_logs.entries[0]["status_code"] == 503
