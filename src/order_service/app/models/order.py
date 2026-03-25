from dataclasses import dataclass
from typing import Optional

@dataclass
class Order:
    id:str
    product_id:str
    quantity:int
    user_id: Optional[str]=None
    status:str= "pending"

    @classmethod
    def from_document(cls, document:dict)-> "Order":
        return cls(
            id=str(document["_id"]),
            product_id=document["product_id"],
            quantity=int(document["quantity"]),
            user_id=document.get("user_id"),
            status=document.get("status", "pending")
        )
        