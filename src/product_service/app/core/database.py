import os

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/product_db")

client = AsyncIOMotorClient(MONGO_URL)
db = client["product_db"]
products_collection = db["products"]
