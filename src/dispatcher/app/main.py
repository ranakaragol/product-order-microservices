from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.security import is_authorized

app= FastAPI()

@app.middleware("http")
async def check_auth(request: Request, call_next):
    #yetkisiz bir işlemse 401 dönmeli
    if not is_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    
    #Her şey doğruysa veya rota başka bir yerse, isteğin geçmesine izin ver
    response= await call_next(request)
    return response

@app.get("/")
def read_root():
    return {"message": "Dispatcher Gateway Running"}
