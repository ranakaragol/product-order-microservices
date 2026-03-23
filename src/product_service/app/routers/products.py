from fastapi import APIRouter

from app.core.database import products_collection as db_products_collection
from app.repositories.product_repository import ProductRepository
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["products"])

# Alias kept explicit so tests can patch this collection.
products_collection = db_products_collection


def get_product_service() -> ProductService:
    repository = ProductRepository(collection_provider=lambda: products_collection)
    return ProductService(repository=repository)
