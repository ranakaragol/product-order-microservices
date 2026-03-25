from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class OrderCreate(BaseModel):
    product_id:str =Field(min_length=1)
    quantity: int=Field(gt=0)

class OrderResponse(BaseModel):
    model_config= ConfigDict(from_attributes=True)

    id:str
    product_id:str
    quantity:int
    user_id:Optional[str] =None
    status: str
