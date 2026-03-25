import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL=os.getenv("MONGO_URL", "mongodb://localhost:27017/order_db")

client=AsyncIOMotorClient(MONGO_URL)
db=client["order_db"]
orders_collection=db["orders"]
