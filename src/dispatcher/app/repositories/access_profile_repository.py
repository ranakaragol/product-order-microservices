import json
import os

from app.core.database import access_profiles_collection

BOOTSTRAP_PROFILES_ENV = "DISPATCHER_ACCESS_PROFILES_BOOTSTRAP"
DEFAULT_AUTHENTICATED_SUBJECT = "default-authenticated"


def _read_only_permissions() -> list[dict]:
    return [
        {"resource": "/products", "methods": ["GET"]},
        {"resource": "/orders", "methods": ["GET"]},
    ]


def _elevated_permissions() -> list[dict]:
    return [
        {"resource": "/products", "methods": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
        {"resource": "/orders", "methods": ["GET", "POST", "PATCH", "DELETE"]},
    ]


def _default_bootstrap_profiles() -> dict[str, dict]:
    return {
        DEFAULT_AUTHENTICATED_SUBJECT: {
            "subject": DEFAULT_AUTHENTICATED_SUBJECT,
            "permissions": _read_only_permissions(),
        },
        "dispatcher-user": {
            "subject": "dispatcher-user",
            "permissions": _elevated_permissions(),
        },
        "alice": {
            "subject": "alice",
            "permissions": _elevated_permissions(),
        },
        "bob": {
            "subject": "bob",
            "permissions": _read_only_permissions(),
        },
    }


def _normalize_profile(document: dict | None) -> dict | None:
    if not isinstance(document, dict):
        return None

    subject = document.get("subject")
    permissions = document.get("permissions")
    if not subject or not isinstance(permissions, list):
        return None

    return document


def _normalize_bootstrap_profiles(raw_profiles) -> dict[str, dict]:
    if isinstance(raw_profiles, list):
        candidate_documents = raw_profiles
    elif isinstance(raw_profiles, dict):
        candidate_documents = raw_profiles.values()
    else:
        return _default_bootstrap_profiles()

    normalized_profiles = {}
    for document in candidate_documents:
        normalized_document = _normalize_profile(document)
        if normalized_document:
            normalized_profiles[normalized_document["subject"]] = normalized_document

    return normalized_profiles or _default_bootstrap_profiles()


def _load_bootstrap_profiles() -> dict[str, dict]:
    raw_profiles = os.getenv(BOOTSTRAP_PROFILES_ENV)
    if not raw_profiles:
        return _default_bootstrap_profiles()

    try:
        parsed_profiles = json.loads(raw_profiles)
    except json.JSONDecodeError:
        return _default_bootstrap_profiles()

    return _normalize_bootstrap_profiles(parsed_profiles)


class AccessProfileRepository:
    def __init__(self, collection=access_profiles_collection, bootstrap_profiles: dict[str, dict] | None = None):
        self._collection = collection
        self._bootstrap_profiles = bootstrap_profiles if bootstrap_profiles is not None else _load_bootstrap_profiles()

    async def seed_bootstrap_profiles(self) -> None:
        if self._collection is None:
            return

        for profile in self._bootstrap_profiles.values():
            await self._persist_profile_if_missing(profile)

    async def get_profile_by_subject(self, subject: str | None) -> dict | None:
        if not subject:
            return None

        persisted_profile = await self._get_persisted_profile(subject)
        if persisted_profile:
            return persisted_profile

        if subject != DEFAULT_AUTHENTICATED_SUBJECT:
            return await self._get_persisted_profile(DEFAULT_AUTHENTICATED_SUBJECT)

        return None

    async def _get_persisted_profile(self, subject: str) -> dict | None:
        if self._collection is None:
            return None

        try:
            document = await self._collection.find_one({"subject": subject})
        except Exception:
            return None

        return _normalize_profile(document)

    async def _persist_profile_if_missing(self, profile: dict) -> None:
        subject = profile["subject"]
        if await self._get_persisted_profile(subject):
            return

        try:
            await self._collection.insert_one(dict(profile))
        except Exception:
            return
