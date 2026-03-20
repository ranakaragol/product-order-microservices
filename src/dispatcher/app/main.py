from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.security import evaluate_authorization

app= FastAPI()

@app.middleware("http")
async def check_auth(request: Request, call_next):
    status_code = evaluate_authorization(request)
    if status_code == 401:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    if status_code == 403:
        return JSONResponse(status_code=403, content={"error": "Forbidden"})
    
    #Her şey doğruysa veya rota başka bir yerse, isteğin geçmesine izin ver
    response= await call_next(request)
    return response

@app.get("/")
def read_root():
    return {"message": "Dispatcher Gateway Running"}
