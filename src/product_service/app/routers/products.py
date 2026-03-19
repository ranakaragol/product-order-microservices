from fastapi import APIRouter
from app.repositories.product_repository import ProductRepository
from app.services.product_service import ProductService


router = APIRouter()


def get_product_service() -> ProductService:
    repository = ProductRepository()
    return ProductService(repository=repository)


@router.get("/products")
async def list_products():
    product_service = get_product_service()
    return await product_service.list_products()
