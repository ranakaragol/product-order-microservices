from app.repositories.product_repository import ProductRepository


class ProductService:
    def __init__(self, repository: ProductRepository):
        self._repository = repository

    async def list_products(self):
        return await self._repository.list_products()
