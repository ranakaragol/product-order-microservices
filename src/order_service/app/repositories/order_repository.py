from typing import Any, Callable, Optional

from bson import ObjectId

from app.models.order import Order


class OrderRepository:
    def __init__(self, collection_provider: Callable[[], Any]):
        self._collection_provider = collection_provider

    @property
    def _collection(self):
        return self._collection_provider()

    async def list_orders(self) -> list[Order]:
        cursor = self._collection.find({})
        documents = await cursor.to_list(length=1000)
        return [Order.from_document(doc) for doc in documents]

    async def get_by_id(self, order_id: str) -> Optional[Order]:
        if not ObjectId.is_valid(order_id):
            return None

        document = await self._collection.find_one({"_id": ObjectId(order_id)})
        if not document:
            return None
        return Order.from_document(document)

    async def create(self, data: dict) -> Order:
        result = await self._collection.insert_one(data)
        created = await self._collection.find_one({"_id": result.inserted_id})
        return Order.from_document(created)

    async def replace(self, order_id: str, data: dict) -> Optional[Order]:
        if not ObjectId.is_valid(order_id):
            return None

        object_id = ObjectId(order_id)
        result = await self._collection.update_one({"_id": object_id}, {"$set": data})
        if result.matched_count == 0:
            return None

        updated = await self._collection.find_one({"_id": object_id})
        return Order.from_document(updated)

    async def patch(self, order_id: str, data: dict) -> Optional[Order]:
        if not ObjectId.is_valid(order_id):
            return None

        patch_doc = {key: value for key, value in data.items() if value is not None}
        if not patch_doc:
            return await self.get_by_id(order_id)

        object_id = ObjectId(order_id)
        result = await self._collection.update_one({"_id": object_id}, {"$set": patch_doc})
        if result.matched_count == 0:
            return None

        updated = await self._collection.find_one({"_id": object_id})
        return Order.from_document(updated)

    async def delete(self, order_id: str) -> bool:
        if not ObjectId.is_valid(order_id):
            return False

        result = await self._collection.delete_one({"_id": ObjectId(order_id)})
        return result.deleted_count > 0
