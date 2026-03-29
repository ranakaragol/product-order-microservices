from app.models.order import Order
from app.repositories.order_repository import OrderRepository


class OrderNotFoundError(Exception): pass

class OrderService:
    def __init__(self, repository:OrderRepository):
        self._repository=repository

    async def list_orders(self):
        return await self._repository.list_orders()

    @staticmethod
    def _compute_total_amount(items: list[dict]) -> float:
        return float(sum(float(item["unit_price"]) * int(item["quantity"]) for item in items))

    async def create_order(self, data: dict) -> Order:
        normalized = {
            "customer_id": data["customer_id"],
            "items": data["items"],
            "status": "pending",
            "total_amount": self._compute_total_amount(data["items"]),
        }
        return await self._repository.create_order(normalized)

    async def get_order(self, order_id:str):
        order=await self._repository.get_by_id(order_id)
        if not order:
            raise OrderNotFoundError()
        return order

    async def patch_order(self, order_id: str, data: dict) -> Order:
        patch_doc = {key: value for key, value in data.items() if value is not None}
        if "items" in patch_doc:
            patch_doc["total_amount"] = self._compute_total_amount(patch_doc["items"])

        updated = await self._repository.patch_order(order_id, patch_doc)
        if not updated:
            raise OrderNotFoundError()
        return updated

    async def delete_order(self, order_id: str) -> None:
        deleted = await self._repository.delete_order(order_id)
        if not deleted:
            raise OrderNotFoundError()
    