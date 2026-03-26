from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
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


ServiceDep = Annotated[ProductService, Depends(get_product_service)]


def _not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Product not found")


@router.get("", response_model=list[ProductResponse])
async def list_products(service: ServiceDep):
    return await service.list_products()


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, service: ServiceDep):
    return await service.create_product(payload.model_dump())


@router.post("/{product_id}/reduce-stock")
async def reduce_stock(product_id: str, data: dict):
    quantity = data.get("quantity")

    if quantity is None or quantity <= 0:
        raise HTTPException(status_code=400, detail="Geçersiz miktar")

    # ObjectId kontrolü
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Geçersiz ürün ID")
    
    result = await products_collection.update_one(
        {
            "_id": ObjectId(product_id),
            "stock": {"$gte": quantity}  # stok yeterli mi
        },
        {
            "$inc": {"stock": -quantity}  # stok düş
        }
    )
    # ürün yok ya da stok yetmedi
    if result.modified_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Stok yetersiz veya ürün bulunamadı"
        )

    return {"message": "Stok başarıyla düşürüldü"}

@router.post("/{product_id}/increase-stock")
async def increase_stock(product_id: str, data: dict):
    quantity = data.get("quantity", 1)

    result = await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$inc": {"stock": quantity}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")

    return {"message": "Stok artırıldı"}

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, service: ServiceDep):
    try:
        return await service.get_product(product_id)
    except ProductNotFoundError as exc:
        raise _not_found_error() from exc


@router.put("/{product_id}", response_model=ProductResponse)
async def replace_product(product_id: str, payload: ProductUpdate, service: ServiceDep):
    try:
        return await service.replace_product(product_id, payload.model_dump())
    except ProductNotFoundError as exc:
        raise _not_found_error() from exc


@router.patch("/{product_id}", response_model=ProductResponse)
async def patch_product(product_id: str, payload: ProductPatch, service: ServiceDep):
    try:
        return await service.patch_product(product_id, payload.model_dump(exclude_unset=True))
    except ProductNotFoundError as exc:
        raise _not_found_error() from exc


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, service: ServiceDep):
    try:
        await service.delete_product(product_id)
    except ProductNotFoundError as exc:
        raise _not_found_error() from exc
