import asyncio
import os
from typing import Iterable, List, Optional, TypedDict

from harborapi import HarborAsyncClient
from harborapi.ext.api import get_artifacts
from harborapi.models import Project
from httpx._config import Timeout
from textual import log
from textual.app import App, ComposeResult
from textual.containers import Container, Grid
from textual.events import MouseEvent, MouseRelease
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, Footer, Header, Input, Static

from ..harbor import get_client
from ..navigation import NavigationMixin, Options, ProgramOption
from .base import BaseScreen
from .repository import RepositoriesScreen


class ProjectSelection(Container):
    projects: reactive[List[Project]] = reactive([], layout=True)
    SCREENS: dict[str, Screen] = {}

    def compose(self) -> ComposeResult:
        self.options = Options(*self._make_project_buttons(), id="project-buttons")
        yield self.options

    def _make_project_buttons(
        self, projects: Optional[List[Project]] = None
    ) -> Iterable[ProgramOption]:
        projects = projects or self.projects
        for project in projects:
            if project.name is None or project.project_id is None:
                log(
                    f"Skipping project with no name or id: {project.name!r}, id={project.project_id!r}"
                )
                continue
            project_id = f"project-{project.project_id}"
            yield Button(project.name, id=project_id)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        # FIXME: memory management
        # maybe instead of 1 screen per repo, we should have 1 screen for all
        # repos, and then update its contents?
        if self.app.is_screen_installed(event.sender.id):
            self.app.push_screen(event.sender.id)
        elif event.sender.id.startswith("project-"):
            project_id = event.sender.id.split("-")[1]
            project = next(
                filter(lambda p: str(p.project_id) == project_id, self.projects), None
            )
            if project is None:
                log(f"Could not find project with id {project_id!r}")
                return
            screen = RepositoriesScreen(name=project.name, id=event.sender.id)
            self.app.install_screen(screen, event.sender.id)
            self.app.push_screen(event.sender.id)
            event.stop()

    async def on_mount(self) -> None:
        asyncio.create_task(self.get_projects())

    async def get_projects(self) -> None:
        client = get_client()
        self.projects = await client.get_projects()
        log(f"Got {len(self.projects)} projects")

    def watch_projects(self, old: list, new: list) -> None:
        diff = list(
            filter(
                lambda p: p.name is not None,
                [p for p in new if p.name not in [p.name for p in old]],
            )
        )
        buttons = self._make_project_buttons(diff)
        self.options.mount(*buttons)


class ProjectsScreen(BaseScreen, NavigationMixin):
    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield ProjectSelection(id="project-selection")
