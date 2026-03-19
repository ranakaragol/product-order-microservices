from app.core.security import create_access_token, get_password_hash, verify_password
from app.repositories.user_repository import UserRepository


class UserAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    async def register(self, username: str, password: str):
        existing_user = await self._user_repository.find_by_username(username)
        if existing_user:
            raise UserAlreadyExistsError()

        hashed_password = get_password_hash(password)
        await self._user_repository.create(username=username, hashed_password=hashed_password)

    async def login(self, username: str, password: str) -> str:
        db_user = await self._user_repository.find_by_username(username)
        if not db_user or not verify_password(password, db_user["password"]):
            raise InvalidCredentialsError()

        return create_access_token(data={"sub": username})
