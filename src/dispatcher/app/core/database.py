import os 
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL=os.getenv("MONGO_URL", "mongodb://dispatcher_mongo:27017")
DB_NAME="dispatcher_db"

# Keep logging fail-open: do not block request handling on Mongo outages.
client = AsyncIOMotorClient(
	MONGO_URL,
	serverSelectionTimeoutMS=500,
	connectTimeoutMS=500,
	socketTimeoutMS=500,
)
db=client[DB_NAME]
logs_collection=db["traffic_logs"]
access_profiles_collection=db["access_profiles"]
