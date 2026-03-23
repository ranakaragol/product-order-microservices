from typing import Any, Callable, Optional

from app.models.product import Product


class ProductRepository:
    def __init__(self, collection_provider: Callable[[], Any]):
        self._collection_provider = collection_provider

    @property
    def _collection(self):
        return self._collection_provider()

    async def list_products(self) -> list[Product]:
        raise NotImplementedError()

    async def get_by_id(self, product_id: str) -> Optional[Product]:
        raise NotImplementedError()

    async def create(self, data: dict) -> Product:
        raise NotImplementedError()

    async def replace(self, product_id: str, data: dict) -> Optional[Product]:
        raise NotImplementedError()

    async def patch(self, product_id: str, data: dict) -> Optional[Product]:
        raise NotImplementedError()

    async def delete(self, product_id: str) -> bool:
        raise NotImplementedError()
