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
            **data,
            "status": "pending"
        }
        result =await self._collection.insert_one(payload)
        created=await self._collection.find_one({"_id": result.inserted_id})
        return Order.from_document(created)
    
    async def get_by_id(self, order_id:str)->Optional[Order]:
        if not ObjectId.is_valid(order_id):
            return None
        doc= await self._collection.find_one({"_id": ObjectId(order_id)})
        return Order.from_document(doc) if doc else None
    
    async def get_orders_by_user(self, user_id: str) -> list[dict]:
        cursor = self._collection.find({"user_id": user_id})
        orders = await cursor.to_list(length=100)
        return orders
    
