from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

from app.core.security import extract_bearer_token, verify_token
from app.repositories.access_profile_repository import AccessProfileRepository

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


@dataclass
class AuthorizationDecision:
    allowed: bool
    status_code: int
    message: str
    context: dict[str, Any] = field(default_factory=dict)


class AuthorizationService:
    """Token validation + per-service/method authorization for gateway traffic."""

    _public_paths = {"/", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, access_profile_repository: AccessProfileRepository):
        self._access_profile_repository = access_profile_repository

    def _get_target_service(self, path: str) -> str | None:
        parts = [part for part in path.split("/") if part]
        if not parts:
            return None
        return parts[0]

    def _resolve_allowed_methods(
        self,
        service_name: str,
        roles: set[str],
        explicit_permissions: dict[str, list[str]] | None,
    ) -> set[str]:
        allowed_methods: set[str] = set()

        for role in roles:
            role_permissions = ROLE_POLICIES.get(role, {})
            allowed_methods.update(role_permissions.get(service_name, set()))

        if explicit_permissions:
            for scoped_service, methods in explicit_permissions.items():
                if scoped_service in {service_name, "*"}:
                    if "*" in methods:
                        allowed_methods.update(ALL_METHODS)
                    else:
                        allowed_methods.update(method.upper() for method in methods)

        return allowed_methods

    async def authorize_request(self, request: Request) -> AuthorizationDecision:
        path = request.url.path
        method = request.method.upper()

        if path.startswith("/auth") or path in self._public_paths:
            return AuthorizationDecision(
                allowed=True,
                status_code=200,
                message="public_route",
                context={"target_service": "auth" if path.startswith("/auth") else "public"},
            )

        target_service = self._get_target_service(path)
        if target_service not in {"products", "orders"}:
            return AuthorizationDecision(
                allowed=True,
                status_code=200,
                message="non_protected_route",
                context={"target_service": target_service or "unknown"},
            )

        token = extract_bearer_token(request.headers.get("Authorization"))
        if not token:
            return AuthorizationDecision(
                allowed=False,
                status_code=401,
                message="missing_or_malformed_bearer_token",
                context={"target_service": target_service},
            )

        payload = verify_token(token)
        if not payload:
            return AuthorizationDecision(
                allowed=False,
                status_code=401,
                message="invalid_token",
                context={"target_service": target_service},
            )

        username = payload.get("sub")
        if not username:
            return AuthorizationDecision(
                allowed=False,
                status_code=401,
                message="token_missing_subject",
                context={"target_service": target_service},
            )

        profile = await self._access_profile_repository.get_profile(username)
        profile_roles = set(profile.get("roles", [])) if profile else set()
        token_roles = set(payload.get("roles", []))
        combined_roles = token_roles | profile_roles
        explicit_permissions = profile.get("service_permissions") if profile else None

        allowed_methods = self._resolve_allowed_methods(
            service_name=target_service,
            roles=combined_roles,
            explicit_permissions=explicit_permissions,
        )

        if method not in allowed_methods:
            return AuthorizationDecision(
                allowed=False,
                status_code=403,
                message=f"forbidden_for_{target_service}_{method}",
                context={
                    "user": username,
                    "target_service": target_service,
                    "roles": sorted(combined_roles),
                },
            )

        return AuthorizationDecision(
            allowed=True,
            status_code=200,
            message="authorized",
            context={
                "user": username,
                "target_service": target_service,
                "roles": sorted(combined_roles),
            },
        )
