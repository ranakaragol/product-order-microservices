from dataclasses import dataclass
from typing import Any


@dataclass
class Order:
    id: str
    customer_id: str
    items: list[dict[str, Any]]
    total_amount: float
    status: str

    @classmethod
    def from_document(cls, document: dict) -> "Order":
        return cls(
            id=str(document["_id"]),
            customer_id=document["customer_id"],
            items=list(document.get("items", [])),
            total_amount=float(document["total_amount"]),
            status=document["status"],
        )
