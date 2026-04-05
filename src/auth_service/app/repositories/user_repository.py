from typing import Any, Callable, Optional

from pymongo import ASCENDING


class UserRepository:
    def __init__(self, collection_provider: Callable[[], Any]):
        self._collection_provider = collection_provider
        self._username_index_ensured = False

    @property
    def _collection(self):
        return self._collection_provider()

    async def _ensure_username_index(self) -> None:
        if self._username_index_ensured:
            return

        collection = self._collection
        create_index = getattr(collection, "create_index", None)
        if callable(create_index):
            await create_index([("username", ASCENDING)], unique=True)

        self._username_index_ensured = True

    async def find_by_username(self, username: str) -> Optional[dict]:
        await self._ensure_username_index()
        return await self._collection.find_one({"username": username})

    async def create_user(self, username: str, hashed_password: str) -> None:
        await self._collection.insert_one({"username": username, "password": hashed_password})
