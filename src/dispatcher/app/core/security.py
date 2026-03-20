import os
from jose import JWTError, jwt

SECRET_KEY = os.getenv("SECRET_KEY", "yazlab-secret-key")
ALGORITHM = "HS256"

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



_authorization_service = AuthorizationService(secret_key=SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str):
    return _authorization_service.verify_token(token)


def extract_bearer_token(auth_header: str | None) -> str | None:
    return _authorization_service._extract_bearer_token(auth_header)
