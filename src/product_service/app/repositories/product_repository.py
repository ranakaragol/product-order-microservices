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
        if not ObjectId.is_valid(product_id):
            return None

        document = await self._collection.find_one({"_id": ObjectId(product_id)})
        if not document:
            return None
        return Product.from_document(document)

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
        if not ObjectId.is_valid(product_id):
            return None

        object_id = ObjectId(product_id)
        update_doc = {
            "name": data["name"],
            "description": data.get("description"),
            "price": float(data["price"]),
            "stock": int(data["stock"]),
        }
        result = await self._collection.update_one(
            {"_id": object_id},
            {"$set": update_doc},
        )
        if result.matched_count == 0:
            return None

        updated = await self._collection.find_one({"_id": object_id})
        return Product.from_document(updated)

    async def patch(self, product_id: str, data: dict) -> Optional[Product]:
        if not ObjectId.is_valid(product_id):
            return None

        patch_doc = {key: value for key, value in data.items() if value is not None}
        if not patch_doc:
            return await self.get_by_id(product_id)

        object_id = ObjectId(product_id)
        result = await self._collection.update_one({"_id": object_id}, {"$set": patch_doc})
        if result.matched_count == 0:
            return None

        updated = await self._collection.find_one({"_id": object_id})
        return Product.from_document(updated)

    async def delete(self, product_id: str) -> bool:
        if not ObjectId.is_valid(product_id):
            return False

        result = await self._collection.delete_one({"_id": ObjectId(product_id)})
        return result.deleted_count > 0
