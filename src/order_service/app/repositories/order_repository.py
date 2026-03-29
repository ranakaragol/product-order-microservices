from typing import Any, Callable, Optional
from bson import ObjectId
from app.models.order import Order

class OrderRepository:
    def __init__(self, collection_provider: Callable[[], Any]):
        self._collection_provider=collection_provider

    @property
    def _collection(self):
        return self._collection_provider()
    
    async def list_orders(self)->list[Order]:
        cursor=self._collection.find({})
        documents=await cursor.to_list(length=1000)
        return [Order.from_document(doc) for doc in documents]
    
    async def create_order(self, data:dict)->Order:
        payload = {
            "customer_id": data["customer_id"],
            "items": data["items"],
            "status": data.get("status", "pending"),
            "total_amount": float(data["total_amount"]),
        }
        result =await self._collection.insert_one(payload)
        created=await self._collection.find_one({"_id": result.inserted_id})
        return Order.from_document(created)
    
    async def get_by_id(self, order_id:str)->Optional[Order]:
        if not ObjectId.is_valid(order_id):
            return None
        doc= await self._collection.find_one({"_id": ObjectId(order_id)})
        return Order.from_document(doc) if doc else None
    
    async def patch_order(self, order_id: str, data: dict) -> Optional[Order]:
        if not ObjectId.is_valid(order_id):
            return None

        object_id = ObjectId(order_id)
        patch_doc = {key: value for key, value in data.items() if value is not None}
        if not patch_doc:
            return await self.get_by_id(order_id)

        result = await self._collection.update_one({"_id": object_id}, {"$set": patch_doc})
        if result.matched_count == 0:
            return None

        updated = await self._collection.find_one({"_id": object_id})
        return Order.from_document(updated)

    async def delete_order(self, order_id: str) -> bool:
        if not ObjectId.is_valid(order_id):
            return False

        result = await self._collection.delete_one({"_id": ObjectId(order_id)})
        return result.deleted_count > 0
    
