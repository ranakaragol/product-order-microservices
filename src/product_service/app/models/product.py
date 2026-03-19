from dataclasses import dataclass
from typing import Optional


@dataclass
class Product:
    id: str
    name: str
    description: Optional[str]
    price: float
    stock: int

    @classmethod
    def from_document(cls, document: dict) -> "Product":
        return cls(
            id=str(document["_id"]),
            name=document["name"],
            description=document.get("description"),
            price=float(document["price"]),
            stock=int(document["stock"]),
        )

    def to_document(self) -> dict:
        return {
            "_id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "stock": self.stock,
        }
