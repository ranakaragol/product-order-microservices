import os 
from fastapi import Request
from jose import JWTError, jwt
from app.repositories.access_profile_repository import AccessProfileRepository

#Token'ları çözmek için Auth servisiyle aynı gizli anahtarı kullanılmalı
SECRET_KEY=os.getenv("SECRET_KEY", "yazlab-secret-key")
ALGORITHM="HS256"
PROTECTED_PREFIXES = ("/products", "/orders")
_access_profile_repository = AccessProfileRepository()

def verify_token(token:str):
    """Token'ı çözer, sahteyse veya süresi dolmuşsa None döner"""
    try:
        payload=jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def _matches_resource_root(path: str, resource: str) -> bool:
    return path == resource or path.startswith(f"{resource}/")


def _is_protected_path(path: str) -> bool:
    return any(_matches_resource_root(path, prefix) for prefix in PROTECTED_PREFIXES)


def get_access_profile_repository() -> AccessProfileRepository:
    return _access_profile_repository


def resolve_access_profile_repository(request: Request) -> AccessProfileRepository:
    repository = getattr(request.app.state, "access_profile_repository", None)
    if repository is not None:
        return repository

    return get_access_profile_repository()


def _is_method_allowed(profile: dict | None, path: str, method: str) -> bool:
    if not profile:
        return False

    normalized_method = method.upper()
    permissions = profile.get("permissions", [])
    for permission in permissions:
        resource = permission.get("resource")
        methods = permission.get("methods", [])
        if resource and _matches_resource_root(path, resource) and normalized_method in {item.upper() for item in methods}:
            return True

    return False


def _extract_bearer_token(auth_header: str | None) -> str | None:
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    parts = auth_header.split(" ", 1)
    if len(parts) != 2:
        return None

    token = parts[1].strip()
    return token or None

async def evaluate_authorization(request: Request) -> int:
    if not _is_protected_path(request.url.path):
        return 200

    token = _extract_bearer_token(request.headers.get("Authorization"))
    if not token:
        return 401

    claims = verify_token(token)
    if not claims:
        return 401

    profile = await resolve_access_profile_repository(request).get_profile_by_subject(claims.get("sub"))
    if not _is_method_allowed(profile, request.url.path, request.method):
        return 403

    return 200
