from dataclasses import dataclass
from typing import Any


@dataclass
class OrderItem:
    product_id: str
    quantity: int
    unit_price: float

    @classmethod
    def from_document(cls, document: dict) -> "OrderItem":
        return cls(
            product_id=document["product_id"],
            quantity=int(document["quantity"]),
            unit_price=float(document["unit_price"]),
        )

    def to_document(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
        }


@dataclass
class Order:
    id: str
    customer_id: str
    items: list[OrderItem]
    status: str = "pending"
    total_amount: float = 0.0

    @classmethod
    def from_document(cls, document: dict) -> "Order":
        return cls(
            id=str(document["_id"]),
            customer_id=document["customer_id"],
            items=[OrderItem.from_document(item) for item in document.get("items", [])],
            status=document.get("status", "pending"),
            total_amount=float(document.get("total_amount", 0.0)),
        )

    def to_document(self) -> dict[str, Any]:
        return {
            "_id": self.id,
            "customer_id": self.customer_id,
            "items": [item.to_document() for item in self.items],
            "status": self.status,
            "total_amount": self.total_amount,
        }
        