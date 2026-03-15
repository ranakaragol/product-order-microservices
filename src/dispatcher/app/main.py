from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .core.security import is_authorized


app= FastAPI()
#Dispatcher için ilk yetkilendirme
@app.middleware("http")
async def check_auth(request: Request, call_next):
    #Core modülü işlemleri yapar
    if not is_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    
    response= await call_next(request)
    return response

@app.get("/")
def read_root():
    return {"message": "Dispatcher Gateway Running"}