from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)
def test_missing_token_returns_401():
    #dispatchera yetki olmadan istek gönderiyoruz
    response=client.get("/products")
    #henüz yetki sistemi olmadığından test başarısız-red olmalı
    assert response.status_code==401

def test_unknown_route_returns_404():
    response=client.get("/olmayan-bir-rota")
    #dispatcher rotayı bulamadığından 404 dönmeli
    assert response.status_code==404
    
