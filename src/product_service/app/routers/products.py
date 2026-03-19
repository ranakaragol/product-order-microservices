from fastapi import APIRouter, HTTPException, status
from app.core.database import products_collection as db_products_collection
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductPatch, ProductResponse, ProductUpdate
from app.services.product_service import ProductService
from app.services.product_service import ProductNotFoundError


router = APIRouter(prefix="/products", tags=["products"])

# Keep this alias for tests that patch routers.products.products_collection.
products_collection = db_products_collection


def get_product_service() -> ProductService:
    repository = ProductRepository(collection_provider=lambda: products_collection)
    return ProductService(repository=repository)


@router.get("", response_model=list[ProductResponse])
async def list_products():
    product_service = get_product_service()
    return await product_service.list_products()


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    product_service = get_product_service()
    try:
        return await product_service.get_product(product_id)
    except ProductNotFoundError:
        raise HTTPException(status_code=404, detail="Product not found")


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate):
    product_service = get_product_service()
    return await product_service.create_product(payload.model_dump())


@router.put("/{product_id}", response_model=ProductResponse)
async def replace_product(product_id: str, payload: ProductUpdate):
    product_service = get_product_service()
    try:
        return await product_service.replace_product(product_id, payload.model_dump())
    except ProductNotFoundError:
        raise HTTPException(status_code=404, detail="Product not found")


@router.patch("/{product_id}", response_model=ProductResponse)
async def patch_product(product_id: str, payload: ProductPatch):
    product_service = get_product_service()
    try:
        return await product_service.patch_product(
            product_id,
            payload.model_dump(exclude_unset=True),
        )
    except ProductNotFoundError:
        raise HTTPException(status_code=404, detail="Product not found")


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str):
    product_service = get_product_service()
    try:
        await product_service.delete_product(product_id)
    except ProductNotFoundError:
        raise HTTPException(status_code=404, detail="Product not found")
