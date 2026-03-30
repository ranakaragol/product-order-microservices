from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.main import app
from app.repositories.access_profile_repository import AccessProfileRepository

pytestmark = pytest.mark.asyncio(loop_scope="function")
SECRET_KEY = "yazlab-secret-key"
DEFAULT_AUTHENTICATED_SUBJECT = "default-authenticated"


class FakeNoopCollection:
    async def find_one(self, query):
        return None


def _token_for_subject(subject: str) -> str:
    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _default_authenticated_profile() -> dict:
    return {
        "subject": DEFAULT_AUTHENTICATED_SUBJECT,
        "permissions": [
            {
                "resource": "/products",
                "methods": ["GET"],
            },
            {
                "resource": "/orders",
                "methods": ["GET"],
            },
        ],
    }


def _elevated_profile(subject: str) -> dict:
    return {
        "subject": subject,
        "permissions": [
            {
                "resource": "/products",
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
            },
            {
                "resource": "/orders",
                "methods": ["GET", "POST", "PATCH", "DELETE"],
            },
        ],
    }


async def test_repository_falls_back_to_default_authenticated_profile_for_real_username():
    repository = AccessProfileRepository(
        collection=FakeNoopCollection(),
        bootstrap_profiles={DEFAULT_AUTHENTICATED_SUBJECT: _default_authenticated_profile()},
    )

    profile = await repository.get_profile_by_subject("real-user-01")

    assert profile == _default_authenticated_profile()


async def test_repository_default_bootstrap_profile_is_read_only(monkeypatch):
    monkeypatch.delenv("DISPATCHER_ACCESS_PROFILES_BOOTSTRAP", raising=False)

    repository = AccessProfileRepository(collection=FakeNoopCollection())
    profile = await repository.get_profile_by_subject("real-user-02")

    assert profile is not None
    product_methods = next(
        permission["methods"]
        for permission in profile["permissions"]
        if permission["resource"] == "/products"
    )
    order_methods = next(
        permission["methods"]
        for permission in profile["permissions"]
        if permission["resource"] == "/orders"
    )
    assert product_methods == ["GET"]
    assert order_methods == ["GET"]


async def test_real_username_token_can_access_products_with_default_authenticated_profile(monkeypatch):
    import app.core.security as security_mod

    repository = AccessProfileRepository(
        collection=FakeNoopCollection(),
        bootstrap_profiles={DEFAULT_AUTHENTICATED_SUBJECT: _default_authenticated_profile()},
    )
    monkeypatch.setattr(security_mod, "get_access_profile_repository", lambda: repository)

    async def fake_forward(request, base_url, path):
        assert path == "products"
        return 200, [{"id": "p-1"}]

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    headers = {"Authorization": f"Bearer {_token_for_subject('real-user-01')}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products", headers=headers)

    assert response.status_code == 200
    assert response.json() == [{"id": "p-1"}]


async def test_real_username_token_is_forbidden_for_product_create_with_default_authenticated_profile(monkeypatch):
    import app.core.security as security_mod

    repository = AccessProfileRepository(
        collection=FakeNoopCollection(),
        bootstrap_profiles={DEFAULT_AUTHENTICATED_SUBJECT: _default_authenticated_profile()},
    )
    monkeypatch.setattr(security_mod, "get_access_profile_repository", lambda: repository)

    async def fake_forward(request, base_url, path):
        return 201, {"id": "p-2"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    headers = {"Authorization": f"Bearer {_token_for_subject('real-user-01')}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/products",
            json={"name": "Mouse", "description": None, "price": 10.0, "stock": 3},
            headers=headers,
        )

    assert response.status_code == 403


async def test_explicit_elevated_subject_can_create_product(monkeypatch):
    import app.core.security as security_mod

    elevated_subject = "alice"
    repository = AccessProfileRepository(
        collection=FakeNoopCollection(),
        bootstrap_profiles={
            DEFAULT_AUTHENTICATED_SUBJECT: _default_authenticated_profile(),
            elevated_subject: _elevated_profile(elevated_subject),
        },
    )
    monkeypatch.setattr(security_mod, "get_access_profile_repository", lambda: repository)

    async def fake_forward(request, base_url, path):
        assert path == "products"
        return 201, {"id": "p-3", "name": "Mouse"}

    monkeypatch.setattr("app.main.forward_request", fake_forward)

    headers = {"Authorization": f"Bearer {_token_for_subject(elevated_subject)}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/products",
            json={"name": "Mouse", "description": None, "price": 10.0, "stock": 3},
            headers=headers,
        )

    assert response.status_code == 201
    assert response.json() == {"id": "p-3", "name": "Mouse"}
