import os 
from fastapi import Request
from jose import JWTError, jwt

#Token'ları çözmek için Auth servisiyle aynı gizli anahtarı kullanılmalı
SECRET_KEY=os.getenv("SECRET_KEY", "yazlab-secret-key")
ALGORITHM="HS256"
PROTECTED_PREFIXES = ("/products", "/orders")
ALLOWED_METHODS = {
    "/products": {"GET"},
    "/orders": {"GET"},
}

def verify_token(token:str):
    """Token'ı çözer, sahteyse veya süresi dolmuşsa None döner"""
    try:
        payload=jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def _is_protected_path(path: str) -> bool:
    return path.startswith(PROTECTED_PREFIXES)


def _is_method_allowed(path: str, method: str) -> bool:
    for prefix, methods in ALLOWED_METHODS.items():
        if path.startswith(prefix):
            return method.upper() in methods
    return True


def _extract_bearer_token(auth_header: str | None) -> str | None:
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    parts = auth_header.split(" ", 1)
    if len(parts) != 2:
        return None

    token = parts[1].strip()
    return token or None

def is_authorized(request: Request)->bool:
    """Gelen istekte yetki-token olup olmadığını ve geçerliliğini kontrol eder"""
    #sadece ürünler ve siparişler rotası korumaya alınıyor
    if _is_protected_path(request.url.path):
        token = _extract_bearer_token(request.headers.get("Authorization"))
        if not token:
            return False

        #Token sahteyse veya süresi geçmişse Reddet
        if not verify_token(token):
            return False
        
    #Diğer rotalariçin şimdilik izin ver
    return True


def evaluate_authorization(request: Request) -> int:
    if not _is_protected_path(request.url.path):
        return 200

    if not is_authorized(request):
        return 401

    if not _is_method_allowed(request.url.path, request.method):
        return 403

    return 200
