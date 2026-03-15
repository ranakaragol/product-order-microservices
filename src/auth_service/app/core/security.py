import jwt
from datetime import datetime, timedelta, timezone

SECRET_KEY="yazlab-secret-key"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
#30 dakikalık bir süre tanımlıyoruz
def create_access_token(data: dict):
    to_encode=data.copy()
    expire=datetime.now(timezone.utc)+timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp":expire})

    #Şifreli JWT token oluşturuyoruz
    encoded_jwt=jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

