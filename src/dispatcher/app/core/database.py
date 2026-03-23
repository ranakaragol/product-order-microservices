import os 
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL=os.getenv("MONGO_URL", "mongodb://dispatcher_mongo:27017")
DB_NAME="dispatcher_db"

client= AsyncIOMotorClient(MONGO_URL)
db=client[DB_NAME]
logs_collection=db["traffic_logs"]

