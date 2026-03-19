import os
import httpx
import logging
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from app.core.security import is_authorized

app= FastAPI()

#Çevresel değişkenlerden Docker için servis adreslerini alıyoruz
#Lokalde çalıştırıyorsak diye varsayılan(8001,8002) portlarını da ekledik
PRODUCT_SERVICE_URL=os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8001")
ORDER_SERVICE_URL=os.getenv("ORDER_SERVICE_URL", "http://localhost:8002")
AUTH_SERVICE_URL=os.getenv("AUTH_SERVICE_URL","http://localhost:8000")

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger("dispatcher")


def _forward_headers(request: Request) -> dict:
    blocked_headers = {"host", "content-length", "connection"}
    return {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in blocked_headers
    }

@app.middleware("http")
async def check_auth(request: Request, call_next):
    #Tüm gelen istekler içi merkezli yetkilendirme kontrolü
    logger.info(f"Incoming request: {request.method} {request.url}")

    if request.url.path.startswith("/auth"):
        return await call_next(request)
    if not is_authorized(request):
        logger.warning("Unauthorized access attempt")
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    
    #Her şey doğruysa veya rota başka bir yerse, isteğin geçmesine izin ver
    response= await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response


#YÖNLENDİRME-ROUTING İŞLEMLERİ
async def forward_request(method:str, url:str, request:Request):
    """İstekleri diğer servislere ileten ve çökmeleri yöneten ortak fonksiyon"""
    try:
        async with httpx.AsyncClient() as client:
            #Gelen isteğin body ve header'larını aynen iletiyoruz
            body=await request.body()
            response= await client.request(
                method=method,
                url=url,
                headers=_forward_headers(request),
                content=body
            )

        #Arka plandaki servis hata döndüyse bunu json olarak ilet
        try:
            resp_content=response.json()
        except:
            resp_content={"detail": response.text}
        
        return JSONResponse(status_code=response.status_code, content=resp_content)
    

    except httpx.RequestError:
        #Ulaşılmayan servisler için HTTP 503 dönmeli
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hedef servise şu an ulaşılamıyor (Service Unavailable)."
        )
    
@app.api_route("/products/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_products(path:str, request: Request):
    url=f"{PRODUCT_SERVICE_URL}/products/{path}"
    return await forward_request(request.method, url, request)
@app.api_route("/orders/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_orders(path:str, request:Request):
    url=f"{ORDER_SERVICE_URL}/orders/{path}"
    return await forward_request(request.method, url, request)
@app.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def route_auth(path:str, request:Request):
    #Dispatcher üzerinden login-register olmak isteyenleri auth servisinde yönlendir
    url=f"{AUTH_SERVICE_URL}/{path}"
    return await forward_request(request.method, url, request)


@app.get("/")
def read_root():
    return {"message": "Dispatcher Gateway Running and Routing..."}
