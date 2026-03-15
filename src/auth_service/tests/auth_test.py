from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_login_failure_returns_401():
    response=client.post("/login", json={"username": "wronguser", "password":"wrongpassword"})
    assert response.status_code==401

def test_login_success_returns_token():
    response=client.post("/login", json={"username": "admin", "password":"password123"})
    assert response.status_code==200
    assert "access_token" in response.json()

    