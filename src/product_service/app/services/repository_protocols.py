from typing import Optional, Protocol

from app.models.product import Product


class ProductRepositoryProtocol(Protocol):
    async def list_products(self) -> list[Product]:
        ...

    async def get_by_id(self, product_id: str) -> Optional[Product]:
        ...

    async def create(self, data: dict) -> Product:
        ...

    async def replace(self, product_id: str, data: dict) -> Optional[Product]:
        ...

    async def patch(self, product_id: str, data: dict) -> Optional[Product]:
        ...

    async def delete(self, product_id: str) -> bool:
        ...