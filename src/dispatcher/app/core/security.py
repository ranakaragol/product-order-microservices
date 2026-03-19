import os 
from fastapi import Request
from jose import JWTError, jwt

#Token'ları çözmek için Auth servisiyle aynı gizli anahtarı kullanılmalı
SECRET_KEY=os.getenv("SECRET_KEY", "yazlab-secret-key")
ALGORITHM="HS256"

def verify_token(token:str):
    """Token'ı çözer, sahteyse veya süresi dolmuşsa None döner"""
    try:
        payload=jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def is_authorized(request: Request)->bool:
    """Gelen istekte yetki-token olup olmadığını ve geçerliliğini kontrol eder"""
    #sadece ürünler ve siparişler rotası korumaya alınıyor
    if request.url.path.startswith("/products") or request.url.path.startswith("/orders"):
        auth_header=request.headers.get("Authorization")

        #Token hiç yoksa veya Bearer ile başlamıyorsa Reddet
        if not auth_header:
            return False
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return False
        #Bearer sahte_token kısmından sadece token'ı al
        token=parts[1]
        #Token sahteyse veya süresi geçmişse Reddet
        if not verify_token(token):
            return False
        
    #Diğer rotalariçin şimdilik izin ver
    return True
