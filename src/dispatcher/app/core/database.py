import os
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/dispatcher_db")


def _resolve_database_name(mongo_url: str) -> str:
    parsed = urlparse(mongo_url)
    db_name = parsed.path.lstrip("/")
    return db_name or "dispatcher_db"


_client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=1000)
_db = _client[_resolve_database_name(MONGO_URL)]


def get_access_profiles_collection():
    return _db["access_profiles"]
