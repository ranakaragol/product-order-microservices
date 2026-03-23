from app.repositories.product_repository import ProductRepository


class ProductNotFoundError(Exception):
    pass


class ProductService:
    def __init__(self, repository: ProductRepository):
        self._repository = repository

    async def list_products(self):
        return await self._repository.list_products()

    async def get_product(self, product_id: str):
        product = await self._repository.get_by_id(product_id)
        if not product:
            raise ProductNotFoundError()
        return product

    async def create_product(self, data: dict):
        return await self._repository.create(data)

    async def replace_product(self, product_id: str, data: dict):
        product = await self._repository.replace(product_id, data)
        if not product:
            raise ProductNotFoundError()
        return product

    async def patch_product(self, product_id: str, data: dict):
        product = await self._repository.patch(product_id, data)
        if not product:
            raise ProductNotFoundError()
        return product

    async def delete_product(self, product_id: str):
        raise NotImplementedError()
