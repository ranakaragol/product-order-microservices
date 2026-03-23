from typing import Any, Callable, Optional

from bson import ObjectId

from app.models.product import Product


class ProductRepository:
    def __init__(self, collection_provider: Callable[[], Any]):
        self._collection_provider = collection_provider

    @property
    def _collection(self):
        return self._collection_provider()

    async def list_products(self) -> list[Product]:
        cursor = self._collection.find({})
        documents = await cursor.to_list(length=1000)
        return [Product.from_document(doc) for doc in documents]

    async def get_by_id(self, product_id: str) -> Optional[Product]:
        raise NotImplementedError()

    async def create(self, data: dict) -> Product:
        payload = {
            "name": data["name"],
            "description": data.get("description"),
            "price": float(data["price"]),
            "stock": int(data["stock"]),
        }
        result = await self._collection.insert_one(payload)
        created = await self._collection.find_one({"_id": result.inserted_id})
        return Product.from_document(created)

    async def replace(self, product_id: str, data: dict) -> Optional[Product]:
        raise NotImplementedError()

    async def patch(self, product_id: str, data: dict) -> Optional[Product]:
        raise NotImplementedError()

    async def delete(self, product_id: str) -> bool:
        raise NotImplementedError()
