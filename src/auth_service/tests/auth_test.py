import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from httpx import ASGITransport, AsyncClient
from jose import jwt
from app.main import app
from app.routers import auth as auth_router


class FakeUsersCollection:
    def __init__(self):
        self._users = {}

    async def find_one(self, query):
        username = query.get("username")
        return self._users.get(username)

    async def insert_one(self, document):
        self._users[document["username"]] = dict(document)
        return {"inserted_id": document["username"]}

@pytest_asyncio.fixture(loop_scope="function", autouse=True)
async def setup_db(monkeypatch):
    fake_db=FakeUsersCollection()
    monkeypatch.setattr(auth_router, "users_collection", fake_db)
    yield

@pytest.mark.asyncio(loop_scope="function")
async def test_register_and_login_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        register = await ac.post("/register", json={
            "username": "user_test_001",
            "password": "testpassword"
        })
        assert register.status_code == 200

        login = await ac.post("/login", json={
            "username": "user_test_001",
            "password": "testpassword"
        })
        assert login.status_code == 200

@pytest.mark.asyncio(loop_scope="function")
async def test_login_with_wrong_password():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        register = await ac.post("/register", json={
            "username": "user_wrong_pwd",
            "password": "right-password"
        })
        assert register.status_code == 200

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/login", json={
            "username": "user_wrong_pwd",
            "password": "wrong-password"
        })

        assert response.status_code == 401


@pytest.mark.asyncio(loop_scope="function")
async def test_register_duplicate_username_returns_409():
    payload = {
        "username": "duplicate_user",
        "password": "same-password",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        first = await ac.post("/register", json=payload)
        second = await ac.post("/register", json=payload)

    assert first.status_code == 200
    assert second.status_code == 409


@pytest.mark.asyncio(loop_scope="function")
async def test_verify_token_valid_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        register = await ac.post("/register", json={
            "username": "user_verify_valid",
            "password": "verify-password"
        })
        assert register.status_code == 200

        login = await ac.post("/login", json={
            "username": "user_verify_valid",
            "password": "verify-password"
        })
        assert login.status_code == 200

        token = login.json()["token"]
        verify = await ac.get("/verify-token", headers={"Authorization": f"Bearer {token}"})

    assert verify.status_code == 200
    assert verify.json()["valid"] is True
    assert verify.json()["user"] == "user_verify_valid"


@pytest.mark.asyncio(loop_scope="function")
async def test_verify_token_invalid_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        verify = await ac.get("/verify-token", headers={"Authorization": "Bearer invalid-token"})

    assert verify.status_code == 401


@pytest.mark.asyncio(loop_scope="function")
async def test_verify_token_missing_header_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        verify = await ac.get("/verify-token")

    assert verify.status_code == 401


@pytest.mark.asyncio(loop_scope="function")
async def test_verify_token_without_sub_claim_returns_401():
    token_without_sub = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=15)},
        "yazlab-secret-key",
        algorithm="HS256",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        verify = await ac.get(
            "/verify-token",
            headers={"Authorization": f"Bearer {token_without_sub}"},
        )

    assert verify.status_code == 401