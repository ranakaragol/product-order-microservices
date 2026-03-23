from fastapi import APIRouter, Header, HTTPException, status

from app.core.database import users_collection as db_users_collection
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, UserCreate
from app.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
)

router = APIRouter()

# Alias is intentionally kept for test patching.
users_collection = db_users_collection


def get_auth_service() -> AuthService:
    repository = UserRepository(collection_provider=lambda: users_collection)
    return AuthService(repository=repository)


@router.post("/register")
async def register(user: UserCreate):
    auth_service = get_auth_service()
    try:
        return await auth_service.register(user.username, user.password)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail="Bu kullanıcı adı zaten mevcut!") from exc


@router.post("/login")
async def login(user: LoginRequest):
    auth_service = get_auth_service()
    try:
        return await auth_service.login(user.username, user.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kullanıcı adı veya şifre",
        ) from exc


@router.get("/verify-token")
async def verify_token_endpoint(authorization: str = Header(...)):
    auth_service = get_auth_service()
    try:
        return auth_service.verify_token_header(authorization)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Geçersiz",
        ) from exc
