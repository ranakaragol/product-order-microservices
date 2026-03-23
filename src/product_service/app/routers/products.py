from fastapi import APIRouter, HTTPException, status

from app.core.database import products_collection as db_products_collection
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductPatch, ProductResponse, ProductUpdate
from app.services.product_service import ProductNotFoundError, ProductService

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


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    service = get_product_service()
    try:
        return await service.get_product(product_id)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Product not found") from exc


@router.put("/{product_id}", response_model=ProductResponse)
async def replace_product(product_id: str, payload: ProductUpdate):
    service = get_product_service()
    try:
        return await service.replace_product(product_id, payload.model_dump())
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Product not found") from exc


@router.patch("/{product_id}", response_model=ProductResponse)
async def patch_product(product_id: str, payload: ProductPatch):
    service = get_product_service()
    try:
        return await service.patch_product(product_id, payload.model_dump(exclude_unset=True))
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Product not found") from exc


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str):
    service = get_product_service()
    try:
        await service.delete_product(product_id)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Product not found") from exc
