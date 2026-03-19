import os 
from fastapi import Request
from jose import JWTError, jwt

#Token'ları çözmek için Auth servisiyle aynı gizli anahtarı kullanılmalı
SECRET_KEY=os.getenv("SECRET_KEY", "yazlab-secret-key")
ALGORITHM="HS256"

class AuthorizationService:
    """Encapsulates authorization checks for dispatcher routes."""

    def __init__(self, secret_key: str, algorithm: str):
        self._secret_key = secret_key
        self._algorithm = algorithm

    def verify_token(self, token: str):
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
            return payload
        except JWTError:
            return None

    def _extract_bearer_token(self, auth_header: str | None) -> str | None:
        if not auth_header:
            return None
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        return parts[1]

    def is_authorized(self, request: Request) -> bool:
        if request.url.path.startswith("/products") or request.url.path.startswith("/orders"):
            auth_header = request.headers.get("Authorization")
            token = self._extract_bearer_token(auth_header)
            if not token:
                return False
            if not self.verify_token(token):
                return False
        return True


_authorization_service = AuthorizationService(secret_key=SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str):
    """Backward-compatible wrapper for token verification."""
    return _authorization_service.verify_token(token)


def is_authorized(request: Request) -> bool:
    """Backward-compatible wrapper for route authorization checks."""
    return _authorization_service.is_authorized(request)
