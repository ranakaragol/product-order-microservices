from typing import Any, Callable, Optional


class UserRepository:
    def __init__(self, collection_provider: Callable[[], Any]):
        self._collection_provider = collection_provider

    @property
    def _collection(self):
        return self._collection_provider()

    async def find_by_username(self, username: str) -> Optional[dict]:
        return await self._collection.find_one({"username": username})

    async def create_user(self, username: str, hashed_password: str) -> None:
        await self._collection.insert_one({"username": username, "password": hashed_password})
