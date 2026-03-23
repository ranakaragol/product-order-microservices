import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app


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
    monkeypatch.setattr("app.main.users_collection", fake_db)
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