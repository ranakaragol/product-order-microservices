from fastapi import APIRouter, Depends, HTTPException, status, Header
from app.core.database import orders_collection as db_collection
from app.repositories.order_repository import OrderRepository
from app.services.order_service import OrderService, OrderNotFoundError, InsufficientStockError, UnauthenticatedError
from app.schemas.order import OrderCreate, OrderResponse


router = APIRouter(prefix="/orders", tags=["orders"])

orders_collection = db_collection

def get_order_service() -> OrderService:
    repository = OrderRepository(collection_provider=lambda: orders_collection)
    return OrderService(repository=repository)

@router.get("", response_model=list[OrderResponse])
async def list_orders(service: OrderService = Depends(get_order_service)):
    return await service.list_orders()

@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate, 
    authorization: str = Header(None), 
    service: OrderService = Depends(get_order_service)
    ):
    try:
        return await service.create_order(payload.model_dump(), token=authorization)
    except UnauthenticatedError:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    except InsufficientStockError:
        raise HTTPException(status_code=400, detail="Insufficient stock or product not found")
    
@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, service: OrderService = Depends(get_order_service)):
    try:
        return await service.get_order(order_id)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Order not found!")