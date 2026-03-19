from typing import Callable, Any


class UserRepository:
    def __init__(self, collection_provider: Callable[[], Any]):
        self._collection_provider = collection_provider

    @property
    def _collection(self):
        return self._collection_provider()

    async def find_by_username(self, username: str):
        return await self._collection.find_one({"username": username})

    async def create(self, username: str, hashed_password: str):
        return await self._collection.insert_one(
            {
                "username": username,
                "password": hashed_password,
            }
        )
