from fastapi import Header
from fastapi import FastAPI,HTTPException, status
from pydantic import BaseModel
from app.core.database import users_collection as db_users_collection
from app.core.security import verify_token
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService, InvalidCredentialsError, UserAlreadyExistsError

app = FastAPI()
# Keep this alias for tests that patch main.users_collection.
users_collection = db_users_collection


def get_auth_service() -> AuthService:
    user_repository = UserRepository(collection_provider=lambda: users_collection)
    return AuthService(user_repository=user_repository)


#Kullanıcıdan gelecek giriş bilgilerinin modelini tanımlıyoruz
class LoginRequest(BaseModel):
    username:str
    password:str
class UserCreate(BaseModel):
    username:str
    password:str

@app.post("/register")
async def register(user: UserCreate):
    auth_service = get_auth_service()
    try:
        await auth_service.register(username=user.username, password=user.password)
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=409,
            detail="Bu kullanıcı adı zaten mevcut!"
        )

    return {"message": "Kullanıcı başarıyla oluşturuldu!"}

@app.post("/login")
async def login(user: LoginRequest):
    auth_service = get_auth_service()
    try:
        token = await auth_service.login(username=user.username, password=user.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kullanıcı adı veya şifre"
        )

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

