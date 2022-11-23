import asyncio
import os
from typing import Iterable, List, Optional, TypedDict, Union

from harborapi import HarborAsyncClient
from harborapi.ext.api import get_artifacts
from harborapi.ext.artifact import ArtifactInfo
from harborapi.models import Project, Repository
from httpx._config import Timeout
from rich.table import Table
from textual import log
from textual.app import App, ComposeResult
from textual.containers import Container, Grid
from textual.events import MouseEvent, MouseRelease
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from ..harbor import get_client
from ..navigation import NavigationMixin, Options, ProgramOption
from .base import BaseScreen


class ArtifactInfoContainer(Container):
    artifact = reactive(None, layout=True)  # type: Optional[ArtifactInfo]

    def compose(self) -> ComposeResult:
        yield

    def on_mount(self) -> None:
        self.render()


class RepositoryScreen(BaseScreen):
    """Screen for displaying a repository's artifacts."""

    pass


class RepositoryPanel(Static):
    repository = reactive(None, layout=True)  # type: Optional[Repository]
    artifacts = reactive([], layout=True)  # type: List[ArtifactInfo]
    fetching = reactive(False, layout=True)

    def render(self) -> Union[Table, str]:
        if self.fetching:
            return "Fetching artifacts..."
        if self.repository is None:
            return "No repository selected"
        if not self.artifacts:
            return "No artifacts found"
        table = Table(
            show_header=True,
            header_style="bold magenta",
            title=self.repository.name,
        )
        table.add_column("Digest")
        table.add_column("Date")
        for artifact in self.artifacts:
            a = artifact.artifact
            table.add_row(str(a.digest), str(a.push_time))
        return table

    def on_mount(self) -> None:
        self.render()
        asyncio.create_task(self.get_artifacts())

    async def get_artifacts(self) -> None:
        self.fetching = True
        client = get_client()
        artifacts = await client.get_artifacts(self.repository)
        self.artifacts = artifacts
        self.fetching = False


class RepoContainer(Container):
    pass


class RepositoryButton(Button):
    repository = reactive(None, layout=True)  # type: Optional[Repository]


class RepositoriesPanel(Widget):
    """Displays a list of repositories in a project."""

    repositories = reactive([], layout=True)  # type: List[Repository]
    project = reactive("")

    def compose(self) -> ComposeResult:
        self.container = RepoContainer()
        yield self.container

    def on_mount(self) -> None:
        asyncio.create_task(self.get_repositories())

    async def get_repositories(self) -> None:
        client = get_client()
        self.repositories = await client.get_repositories(self.project)
        print(self.repositories)

    async def watch_repositories(
        self, old: List[Repository], new: List[Repository]
    ) -> None:
        """Watch for changes to repositories."""
        if old == new:
            return

        for repo in new:
            if repo not in old:
                button = RepositoryButton(
                    repo.name,
                    id=repo.name,  # FIXME: can fail if name is None or numbers
                )
                button.repository = repo
                self.container.mount(button)


class RepositoriesScreen(BaseScreen):
    def compose(self) -> ComposeResult:
        yield from super().compose()
        self.panel = RepositoriesPanel()
        self.panel.project = self.name
        yield Container(self.panel, id="repositories")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if not isinstance(event.sender, RepositoryButton):
            return
        event.stop()
        if self.app.is_screen_installed(event.sender.repository.name):
            self.app.push_screen(event.sender.repository.name)
            return
        screen = RepositoryScreen(
            name=event.sender.repository.name,
            id=event.sender.repository.name,
        )
        # self.app.install_screen(

        self.panel.remove()
        self.panel = RepositoryPanel()
        self.panel.repository = event.sender.repository
        self.screen.query_one("#repositories").mount(self.panel)
