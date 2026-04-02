from contextlib import asynccontextmanager

from fastapi import FastAPI


class DispatcherBootstrapper:
    def __init__(self, *, access_profile_repository_factory):
        self._access_profile_repository_factory = access_profile_repository_factory

    async def seed_dispatcher_access_profiles(self, app: FastAPI | None = None) -> None:
        repository = getattr(app.state, "access_profile_repository", None) if app is not None else None
        if repository is None:
            repository = self._access_profile_repository_factory()

        await repository.seed_bootstrap_profiles()

    def build_lifespan(self):
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await self.seed_dispatcher_access_profiles(app)
            yield

        return lifespan
