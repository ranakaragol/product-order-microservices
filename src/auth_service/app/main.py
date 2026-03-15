from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from .core.security import create_access_token

app = FastAPI()

#Kullanıcıdan gelecek giriş bilgilerinin modelini tanımlıyoruz
class LoginRequest(BaseModel):
    username:str
    password:str


@app.post("/login")
def login(request: LoginRequest):
    #Doğru kullanıcı adı ve şifre
    if request.username=="admin" and request.password=="password123":
        access_token=create_access_token(data={"sub": request.username})
        return {"access_token": access_token, "token_type": "bearer"}
    #Yanlış bilgide 401 Yetkisiz hatası
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz kullanıcı adı ve şifre"
    )