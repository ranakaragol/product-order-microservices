from app.repositories.order_repository import OrderRepository


class OrderNotFoundError(Exception):
    pass


class OrderService:
    def __init__(self, repository: OrderRepository):
        self._repository = repository

    @staticmethod
    def _calculate_total(items: list[dict]) -> float:
        return float(sum(item["quantity"] * item["unit_price"] for item in items))

    async def list_orders(self):
        return await self._repository.list_orders()

    async def get_order(self, order_id: str):
        order = await self._repository.get_by_id(order_id)
        if not order:
            raise OrderNotFoundError()
        return order

    async def create_order(self, data: dict):
        payload = {
            "customer_id": data["customer_id"],
            "items": data["items"],
            "total_amount": self._calculate_total(data["items"]),
            "status": data.get("status", "created"),
        }
        return await self._repository.create(payload)

    async def replace_order(self, order_id: str, data: dict):
        payload = {
            "customer_id": data["customer_id"],
            "items": data["items"],
            "total_amount": self._calculate_total(data["items"]),
            "status": data["status"],
        }
        order = await self._repository.replace(order_id, payload)
        if not order:
            raise OrderNotFoundError()
        return order

    async def patch_order(self, order_id: str, data: dict):
        payload = dict(data)
        if "items" in payload and payload["items"] is not None:
            payload["total_amount"] = self._calculate_total(payload["items"])

        order = await self._repository.patch(order_id, payload)
        if not order:
            raise OrderNotFoundError()
        return order

    async def delete_order(self, order_id: str):
        deleted = await self._repository.delete(order_id)
        if not deleted:
            raise OrderNotFoundError()
