from fastapi import APIRouter, status

from app.core.database import products_collection as db_products_collection
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductResponse
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["products"])

# Alias kept explicit so tests can patch this collection.
products_collection = db_products_collection


def get_product_service() -> ProductService:
    repository = ProductRepository(collection_provider=lambda: products_collection)
    return ProductService(repository=repository)


@router.get("", response_model=list[ProductResponse])
async def list_products():
    service = get_product_service()
    return await service.list_products()


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate):
    service = get_product_service()
    return await service.create_product(payload.model_dump())
