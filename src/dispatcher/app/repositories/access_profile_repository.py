import json
import logging
import os
from typing import Any

from app.core.database import get_access_profiles_collection

logger = logging.getLogger("dispatcher.authz")


class AccessProfileRepository:
    """Reads per-user authorization profiles from dispatcher isolated storage."""

    def __init__(self):
        self._collection = get_access_profiles_collection()
        self._fallback_profiles = self._load_bootstrap_profiles()

    def _load_bootstrap_profiles(self) -> dict[str, dict[str, Any]]:
        profiles: dict[str, dict[str, Any]] = {}

        raw_profiles = os.getenv("DISPATCHER_ACCESS_PROFILES_JSON", "")
        if not raw_profiles:
            return profiles

        try:
            parsed = json.loads(raw_profiles)
        except json.JSONDecodeError:
            logger.warning("invalid_dispatcher_access_profiles_json")
            return profiles

        if isinstance(parsed, list):
            for profile in parsed:
                username = profile.get("username") if isinstance(profile, dict) else None
                if username:
                    profiles[username] = profile

        return profiles

    async def get_profile(self, username: str) -> dict[str, Any] | None:
        try:
            profile = await self._collection.find_one({"username": username}, {"_id": 0})
            if profile:
                return profile
        except Exception as exc:
            logger.warning("access_profile_lookup_failed username=%s error=%s", username, exc)

        return self._fallback_profiles.get(username)
