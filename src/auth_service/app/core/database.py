import os 
from motor.motor_asyncio import AsyncIOMotorClient

#Docker üzerinden gelirse mongo_url, yoksa yerel adres kullanılır
MONGO_URL=os.getenv("MONGO_URL", "mongodb://localhost:27017/auth_db")

#Asenkron mongodb istemcisi oluşturulur ve veritabanı seçilir
client=AsyncIOMotorClient(MONGO_URL)
db = client["auth_db"]
#Kullanıcıların tutulacağı koleksiyon
users_collection=db.db["users"]

