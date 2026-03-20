import logging
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.security import is_authorized
from app.gateway import router as gateway_router

app= FastAPI()
app.include_router(gateway_router)

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger("dispatcher")

@app.middleware("http")
async def check_auth(request: Request, call_next):
    #Tüm gelen istekler içi merkezli yetkilendirme kontrolü
    logger.info(f"Incoming request: {request.method} {request.url}")

    if request.url.path.startswith("/auth"):
        return await call_next(request)
    if not is_authorized(request):
        status_code = getattr(request.state, "auth_status_code", 401)
        logger.warning("Unauthorized access attempt")
        error = "Unauthorized" if status_code == 401 else "Forbidden"
        return JSONResponse(status_code=status_code, content={"error": error})
    
    #Her şey doğruysa veya rota başka bir yerse, isteğin geçmesine izin ver
    response= await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

@app.get("/")
def read_root():
    return {"message": "Dispatcher Gateway Running and Routing..."}
