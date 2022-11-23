from dataclasses import MISSING, dataclass, field
from functools import lru_cache, wraps
from typing import Dict, Iterable, List, Optional

from harborapi import HarborAsyncClient
from harborapi.ext.api import get_artifacts
from harborapi.ext.artifact import ArtifactInfo
from harborapi.models import Artifact, Project, Repository
from textual.app import App
from textual.widgets import TextLog

from .config import HarborSettings

# Mutable globals are obviously not ideal, but I'm not sure how to share
# state between widgets in Textual. Ideally, we want to have access to
# the config and client in all widgets, and I'm not sure how to do that without
# using a global.
_CLIENT: Optional["CachedHarborClient"] = None


def init_client(client: HarborAsyncClient, app: App) -> None:
    global _CLIENT
    cached_client = CachedHarborClient(client=client, app=app)
    _CLIENT = cached_client


def get_client() -> "CachedHarborClient":
    if _CLIENT is None:
        raise ValueError("Client not initialized")
    return _CLIENT


def log_after(f):
    """Decorator that logs the result of a Harbor API call after it completes."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        self = args[0]
        args = args[1:]
        try:
            return f(self, *args, **kwargs)
        finally:
            self.log_response()

    return wrapper


class CachedHarborClient:
    """Abstraction over HarborAsyncClient that caches results in-memory."""

    def __init__(self, client: HarborAsyncClient, app: App) -> None:
        self.client = client
        self.app = app

    def __hash__(self) -> str:
        return hash(self.client.url + self.client.credentials)

    def clear(self, attr_name: Optional[str] = None) -> None:
        """Clears the cached data the given attribute or all attributes."""

        def clear(attr_name: str) -> None:
            attr = getattr(self, attr_name)
            if hasattr(attr, "clear_cache"):
                attr.clear_cache()

        if attr_name:
            clear(attr_name)
        else:
            for attr_name in self.__dict__:
                clear(attr_name)

    def log_response(self) -> None:
        resp = self.client.last_response
        if not resp:
            return
        logline = f"{resp.method} {resp.url}: {resp.status_code}"
        self.app.query_one("#debug-log", TextLog).write(logline)

    # @lru_cache(maxsize=20)
    @log_after
    async def get_artifacts(self, repo: Repository) -> List[ArtifactInfo]:
        repos = [repo] if repo else None
        return await get_artifacts(self.client, repos=repos)

    @lru_cache(maxsize=20)
    @log_after
    async def get_projects(self) -> List[Project]:
        return await self.client.get_projects()

    @lru_cache(maxsize=20)
    @log_after
    async def get_repositories(self, project_name: str) -> List[Repository]:
        return await self.client.get_repositories(project_name)


# DEPRECATED: probably easier to just use lru_cache
@dataclass
class HarborClientDclass:
    """Abstraction over HarborAsyncClient that manages state and caching."""

    client: HarborAsyncClient
    projects: List[Project] = field(default_factory=list)
    repositories: Dict[str, Repository] = field(default_factory=dict)
    artifacts: List[Artifact] = field(default_factory=list)
    artifactinfo: Dict[str, ArtifactInfo] = field(default_factory=dict)
    """Mapping of digest to ArtifactInfo"""

    @property
    def all_repositories(self) -> Iterable[Repository]:
        for repos in self.repositories.values():
            yield from repos

    def __hash__(self) -> str:
        return hash(self.client.url + self.client.credentials)

    def clear(self, attr: Optional[str] = None) -> None:
        """Clears the cached data the given attribute or all attributes."""

        def clear_field(attr: str) -> None:
            field = self.__dataclass_fields__.get(attr)
            if field is None:
                raise AttributeError(f"Unknown field {attr}")
            if field.default is not MISSING:
                setattr(self, attr, field.default)
            elif not all(field.default_factory is not x for x in (MISSING, None)):
                setattr(self, attr, field.default_factory())
            else:
                raise AttributeError(f"Cannot clear field {attr}")

        if attr is not None:
            clear_field(attr)
        else:
            for field in self.__dataclass_fields__:
                clear_field(field)

    async def get_projects(self) -> List[Project]:
        # We have already fetched the projects, so return them
        if self.projects:
            return self.projects
        self.projects = await self.client.get_projects()
        return self.projects

    async def get_repositories(self, project_name: str) -> List[Repository]:
        # We have already fetched the repositories, so return them
        if repos := self.repositories.get(project_name):
            return repos
        self.repositories[project_name] = await self.client.get_repositories(
            project_name
        )
        return self.repositories[project_name]
