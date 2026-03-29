from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrderItemInput(BaseModel):
    product_id: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)


class OrderCreate(BaseModel):
    customer_id: str = Field(min_length=1)
    items: list[OrderItemInput] = Field(min_length=1)


class OrderPatch(BaseModel):
    customer_id: Optional[str] = Field(default=None, min_length=1)
    items: Optional[list[OrderItemInput]] = None
    status: Optional[str] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    items: list[OrderItemInput]
    status: str
    total_amount: float
