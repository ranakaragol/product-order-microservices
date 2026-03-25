from app.repositories.order_repository import OrderRepository
from app.models.order import Order

class OrderNotFoundError(Exception):
    pass

class OrderService:
    def __init__(self, repository:OrderRepository):
        self._repository=repository

    async def list_orders(self)->list[Order]:
        return await self._repository.list_orders()
    async def create_order(self, data:dict)->Order:
        return await self._repository.create_order(data)
    async def get_order(self, order_id:str)->Order:
        order=await self._repository.get_by_id(order_id)
        if not order:
            raise OrderNotFoundError()
        return order
    