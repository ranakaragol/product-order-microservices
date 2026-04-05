from typing import Optional, Protocol

from app.models.order import Order


class OrderRepositoryProtocol(Protocol):
    async def list_orders(self, *, skip: int = 0, limit: int = 100) -> list[Order]:
        ...

    async def create_order(self, data: dict) -> Order:
        ...

    async def get_by_id(self, order_id: str) -> Optional[Order]:
        ...

    async def patch_order(self, order_id: str, data: dict) -> Optional[Order]:
        ...

    async def delete_order(self, order_id: str) -> bool:
        ...