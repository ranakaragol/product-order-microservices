from app.repositories.product_repository import ProductRepository


class ProductNotFoundError(Exception):
    pass


class ProductService:
    def __init__(self, repository: ProductRepository):
        self._repository = repository

    async def list_products(self):
        return await self._repository.list_products()

    async def get_product(self, product_id: str):
        raise NotImplementedError()

    async def create_product(self, data: dict):
        return await self._repository.create(data)

    async def replace_product(self, product_id: str, data: dict):
        raise NotImplementedError()

    async def patch_product(self, product_id: str, data: dict):
        raise NotImplementedError()

    async def delete_product(self, product_id: str):
        raise NotImplementedError()
