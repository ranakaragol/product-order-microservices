from app.core.security import create_access_token, get_password_hash, verify_password, verify_token
from app.repositories.user_repository import UserRepository


class UserAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


class AuthService:
    def __init__(self, repository: UserRepository):
        self._repository = repository

    async def register(self, username: str, password: str) -> dict:
        existing_user = await self._repository.find_by_username(username)
        if existing_user:
            raise UserAlreadyExistsError()

        hashed_password = get_password_hash(password)
        await self._repository.create_user(username, hashed_password)
        return {"message": "Kullanıcı başarıyla oluşturuldu!"}

    async def login(self, username: str, password: str) -> dict:
        db_user = await self._repository.find_by_username(username)
        if not db_user or not verify_password(password, db_user["password"]):
            raise InvalidCredentialsError()

        token = create_access_token(data={"sub": username})
        return {"message": "Giriş başarılı", "token": token}

    def verify_token_header(self, authorization: str) -> dict:
        token = authorization.replace("Bearer ", "")
        payload = verify_token(token)
        if payload is None:
            raise InvalidTokenError()

        return {"valid": True, "user": payload["sub"]}
