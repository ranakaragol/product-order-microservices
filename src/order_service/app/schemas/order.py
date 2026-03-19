from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrderItem(BaseModel):
    product_id: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    unit_price: float = Field(gt=0)


class OrderCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=120)
    items: list[OrderItem] = Field(min_length=1)
    status: str = Field(default="created", min_length=1, max_length=50)


class OrderUpdate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=120)
    items: list[OrderItem] = Field(min_length=1)
    status: str = Field(min_length=1, max_length=50)


class OrderPatch(BaseModel):
    customer_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    items: Optional[list[OrderItem]] = Field(default=None, min_length=1)
    status: Optional[str] = Field(default=None, min_length=1, max_length=50)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    items: list[OrderItem]
    total_amount: float
    status: str
