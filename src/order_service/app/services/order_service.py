import httpx
import os
from app.repositories.order_repository import OrderRepository
from app.models.order import Order

PRODUCT_SERVICE_URL=os.getenv("PRODUCT_SERVICE_URL", "http://product_service:8000")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8000")

class OrderNotFoundError(Exception): pass
class InsufficientStockError(Exception): pass
class UnauthenticatedError(Exception): pass

class OrderService:
    def __init__(self, repository:OrderRepository):
        self._repository=repository

    async def list_orders(self):
        return await self._repository.list_orders()
    
    async def create_order(self, data:dict, token:str=None)->Order:
        async with httpx.AsyncClient() as client:
            try:
                auth_res = await client.get(
                    f"{AUTH_SERVICE_URL}/verify-token",
                    headers={"Authorization": token} if token else {}
                )
                if auth_res.status_code != 200:
                    raise UnauthenticatedError()
            except httpx.HTTPError:
                raise UnauthenticatedError()
            
        async with httpx.AsyncClient() as client:

            try:
                response= await client.get(f"{PRODUCT_SERVICE_URL}/products/{data['product_id']}")
                if response.status_code!=200:
                    raise InsufficientStockError()
                product=response.json()
                if product["stock"]<data["quantity"]:
                    raise InsufficientStockError()
                
            except(httpx.HTTPError, KeyError):
                raise InsufficientStockError()

        return await self._repository.create_order(data)
    
    async def get_order(self, order_id:str):
        order=await self._repository.get_by_id(order_id)
        if not order:
            raise OrderNotFoundError()
        return order
    