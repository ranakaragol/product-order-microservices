import json
import os
from fastapi import Request
from jose import JWTError, jwt

SECRET_KEY = os.getenv("SECRET_KEY", "yazlab-secret-key")
ALGORITHM = "HS256"
ALL_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

ROLE_POLICIES: dict[str, dict[str, set[str]]] = {
    "admin": {
        "products": set(ALL_METHODS),
        "orders": set(ALL_METHODS),
    },
    "catalog_reader": {
        "products": {"GET"},
    },
    "catalog_manager": {
        "products": set(ALL_METHODS),
    },
    "order_reader": {
        "orders": {"GET"},
    },
    "order_manager": {
        "orders": set(ALL_METHODS),
    },
}

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

    def _parse_bootstrap_profiles(self) -> dict[str, dict]:
        raw_profiles = os.getenv("DISPATCHER_ACCESS_PROFILES_JSON", "")
        if not raw_profiles:
            return {}

        try:
            parsed = json.loads(raw_profiles)
        except json.JSONDecodeError:
            return {}

        profiles = {}
        if isinstance(parsed, list):
            for profile in parsed:
                if isinstance(profile, dict) and profile.get("username"):
                    profiles[profile["username"]] = profile
        return profiles

    def _allowed_methods_for(self, service_name: str, payload: dict, profile: dict | None) -> set[str]:
        token_roles = set(payload.get("roles", []))
        profile_roles = set(profile.get("roles", [])) if profile else set()
        combined_roles = token_roles | profile_roles

        allowed_methods: set[str] = set()
        for role in combined_roles:
            allowed_methods.update(ROLE_POLICIES.get(role, {}).get(service_name, set()))

        explicit_permissions = profile.get("service_permissions", {}) if profile else {}
        for scoped_service, methods in explicit_permissions.items():
            if scoped_service not in {service_name, "*"}:
                continue
            if "*" in methods:
                allowed_methods.update(ALL_METHODS)
            else:
                allowed_methods.update(method.upper() for method in methods)

        return allowed_methods

    def is_authorized(self, request: Request) -> bool:
        path = request.url.path
        method = request.method.upper()

        if path.startswith("/products") or path.startswith("/orders"):
            target_service = "products" if path.startswith("/products") else "orders"

            auth_header = request.headers.get("Authorization")
            token = self._extract_bearer_token(auth_header)
            if not token:
                request.state.auth_status_code = 401
                return False

            payload = self.verify_token(token)
            if not payload:
                request.state.auth_status_code = 401
                return False

            username = payload.get("sub")
            if not username:
                request.state.auth_status_code = 401
                return False

            profiles = self._parse_bootstrap_profiles()
            profile = profiles.get(username)
            allowed_methods = self._allowed_methods_for(target_service, payload, profile)
            if method not in allowed_methods:
                request.state.auth_status_code = 403
                return False

            request.state.auth_status_code = 200
        return True


_authorization_service = AuthorizationService(secret_key=SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str):
    """Backward-compatible wrapper for token verification."""
    return _authorization_service.verify_token(token)


def is_authorized(request: Request) -> bool:
    """Backward-compatible wrapper for route authorization checks."""
    return _authorization_service.is_authorized(request)
