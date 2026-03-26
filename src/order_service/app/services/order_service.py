import httpx
import os
from app.repositories.order_repository import OrderRepository
from app.models.order import Order
from bson import ObjectId

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
    
    async def _get(self, url: str, headers: dict = None):
        async with httpx.AsyncClient() as client:
            return await client.get(url, headers=headers)
    
    #sipariş oluştur
    async def create_order(self, data: dict, token: str = None) -> Order:
        async with httpx.AsyncClient() as client:
            #auth check
            try:
                auth_res = await self._get(
                    f"{AUTH_SERVICE_URL}/verify-token",
                    headers={"Authorization": token} if token else {}
                )
                if auth_res.status_code != 200:
                    raise UnauthenticatedError()
                
                user_info = auth_res.json()
                print(f"DEBUG: User Info from Auth: {user_info}")
                data["user_id"] = (
                    user_info.get("user") or 
                    "unknown_user"
                )

            except httpx.HTTPError:
                raise UnauthenticatedError()
                
            try:
                reduce_url = f"{PRODUCT_SERVICE_URL}/products/{data['product_id']}/reduce-stock"

                async with httpx.AsyncClient() as client:
                    stock_res = await client.post(
                        reduce_url,
                        json={"quantity": data["quantity"]}
                    )

                if stock_res.status_code != 200:
                    raise InsufficientStockError()

            except (httpx.HTTPError, KeyError):
                raise InsufficientStockError()

            return await self._repository.create_order(data)
        
    #sipariş iptal
    async def cancel_order(self, order_id: str, token: str = None):
        order = await self._repository.get_by_id(order_id)

        if not order:
            raise OrderNotFoundError()

        if order.status == "cancelled":
            return order

        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(
                    f"{PRODUCT_SERVICE_URL}/products/{order.product_id}/increase-stock",
                    json={"quantity": order.quantity}
                )

                if res.status_code != 200:
                    raise InsufficientStockError()

            except httpx.HTTPError:
                raise InsufficientStockError()

        # status güncelle
        await self._repository._collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": "cancelled"}}
        )

        return await self._repository.get_by_id(order_id)

    async def get_order(self, order_id:str):
        order=await self._repository.get_by_id(order_id)
        if not order:
            raise OrderNotFoundError()
        return order
    
    async def get_my_orders(self, token: str) -> list[Order]:
        async with httpx.AsyncClient() as client:
            # token auth service ile doğrula
            auth_res = await client.get(
                f"{AUTH_SERVICE_URL}/verify-token",
                headers={"Authorization": token}
            )
            
            if auth_res.status_code != 200:
                raise UnauthenticatedError() 
            
            user_info = auth_res.json()
            user_id = user_info.get("user") or user_info.get("sub")
            
        # sadece o kullanıcıya ait veriler gelir
        orders_data = await self._repository.get_orders_by_user(user_id)
        return [Order(**order) for order in orders_data]
    