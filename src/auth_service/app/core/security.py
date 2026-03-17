from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
import bcrypt
import os 

SECRET_KEY=os.getenv("SECRET_KEY","yazlab-secret-key")
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

#Şifre maskelenir
def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

def verify_token(token: str):
    try:
        payload=jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
    