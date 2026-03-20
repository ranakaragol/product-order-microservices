from fastapi import APIRouter, HTTPException, status

from app.core.database import orders_collection as db_orders_collection
from app.repositories.order_repository import OrderRepository
from app.schemas.order import OrderCreate, OrderPatch, OrderResponse, OrderUpdate
from app.services.order_service import OrderNotFoundError, OrderService

router = APIRouter(prefix="/orders", tags=["orders"])

# Keep this alias for tests that patch routers.orders.orders_collection.
orders_collection = db_orders_collection


def get_order_service() -> OrderService:
    repository = OrderRepository(collection_provider=lambda: orders_collection)
    return OrderService(repository=repository)


@router.get("", response_model=list[OrderResponse])
async def list_orders():
    order_service = get_order_service()
    return await order_service.list_orders()


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str):
    order_service = get_order_service()
    try:
        return await order_service.get_order(order_id)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Order not found")


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate):
    order_service = get_order_service()
    return await order_service.create_order(payload.model_dump())


@router.put("/{order_id}", response_model=OrderResponse)
async def replace_order(order_id: str, payload: OrderUpdate):
    order_service = get_order_service()
    try:
        return await order_service.replace_order(order_id, payload.model_dump())
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Order not found")


@router.patch("/{order_id}", response_model=OrderResponse)
async def patch_order(order_id: str, payload: OrderPatch):
    order_service = get_order_service()
    try:
        return await order_service.patch_order(
            order_id,
            payload.model_dump(exclude_unset=True),
        )
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Order not found")


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(order_id: str):
    order_service = get_order_service()
    try:
        await order_service.delete_order(order_id)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Order not found")
