import pytest
import pytest_asyncio
import uuid
import os
from httpx import ASGITransport, AsyncClient
from app.main import app
import motor.motor_asyncio

# Yeni sürüm pytest-asyncio kullanımı
@pytest_asyncio.fixture(loop_scope="function", autouse=True)
async def setup_db():
    from app import main
    mongo_url = os.getenv("TEST_MONGO_URL", "mongodb://localhost:27017")
    main.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
    main.db = main.client["test_auth_db"]
    main.users_collection = main.db["users"]
    yield
    main.client.close()

@pytest.mark.asyncio(loop_scope="function")
async def test_register_and_login_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        unique_user = f"user_{uuid.uuid4().hex[:6]}"
        # Kayıt
        register= await ac.post("/register", json={
            "username": unique_user,
            "password": "testpassword"
        })
        # Giriş
        assert register.status_code==200

        login = await ac.post("/login", json={
            "username": unique_user,
            "password": "testpassword"
        })
        assert login.status_code == 200

@pytest.mark.asyncio(loop_scope="function")
async def test_login_with_wrong_password():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Var olmayan kullanıcı
        response = await ac.post("/login", json={
            "username": "hic_yok_boyle_biri",
            "password": "123"
        })
        
        # Burada uygulamanın döndüğü hata 401 
        assert response.status_code == 401