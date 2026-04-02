from typing import Optional, Protocol


class UserRepositoryProtocol(Protocol):
    async def find_by_username(self, username: str) -> Optional[dict]:
        ...

    async def create_user(self, username: str, hashed_password: str) -> None:
        ...