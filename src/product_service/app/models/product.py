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
