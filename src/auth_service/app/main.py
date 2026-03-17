from fastapi import Header
from fastapi import FastAPI,HTTPException, status
from pydantic import BaseModel
from app.core.database import users_collection
from app.core.security import verify_password, create_access_token, get_password_hash, verify_token

app = FastAPI()
#Kullanıcıdan gelecek giriş bilgilerinin modelini tanımlıyoruz
class LoginRequest(BaseModel):
    username:str
    password:str
class UserCreate(BaseModel):
    username:str
    password:str

@app.post("/register")
async def register(user: UserCreate):
    #Kullanıcı olup olmadığı kontrol edilir
    existing_user=await users_collection.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Bu kullanıcı adı zaten mevcut!"
        )
    
    #Şifreyi hashle ve veritabanına kaydet
    hashed_password=get_password_hash(user.password)
    new_user={
        "username": user.username,
        "password" :hashed_password
    }
    await users_collection.insert_one(new_user)
    return {"message": "Kullanıcı başarıyla oluşturuldu!"}

@app.post("/login")
async def login(user: LoginRequest):
    db_user = await users_collection.find_one({"username": user.username})
    
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kullanıcı adı veya şifre"
        )
    
    token = create_access_token(data={"sub": user.username})
    
    return {
        "message": "Giriş başarılı",
        "token": token
    }
@app.get("/verify-token")
async def verify_token_endpoint(authorization: str= Header(...)):
    token = authorization.replace("Bearer ", "")
    payload=verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Geçersiz"
        )
    return {
        "valid":True,
        "user": payload["sub"]
    }

