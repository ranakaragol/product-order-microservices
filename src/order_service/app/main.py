from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class OrderCreate(BaseModel):
    product_id:str
    quantity:int

@app.get("/orders")
async def list_orders():
    return []

@app.post("/orders", status_code=201)
async def create_order(order: OrderCreate):
    return {"id": "123", "product_id":order.product_id, "quantity": order.quantity}

@app.get("/orders/{order_id}")
async def get_order(order_id:str):
    return {"id":order_id, "product_id":"123", "quantity":1}

@app.get("/")
def root():
    return {"message": "service running"}
