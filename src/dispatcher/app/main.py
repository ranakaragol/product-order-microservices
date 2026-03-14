from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app= FastAPI()
#Dispatcher için ilk yetkilendirme
@app.middleware("http")
async def check_auth(request: Request, call_next):
    #istek "/products" rotasına geliyorsa ve Header'da yetki yoksa..
    #401 yetkisiz- Unauthorized hatası
    if request.url.path.startswith("/products"):
        if "Authorization" not in request.headers:
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    #Her şey doğruysa veya rota başka bir yerse, isteğin geçmesine izin ver
    response= await call_next(request)
    return response

@app.get("/")
def read_root():
    return {"message": "Dispatcher Gateway Running"}