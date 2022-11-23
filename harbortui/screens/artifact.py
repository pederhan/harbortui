import asyncio
import os
from typing import Iterable, List, Optional, TypedDict

from harborapi import HarborAsyncClient
from harborapi.ext.api import get_artifacts
from harborapi.ext.artifact import ArtifactInfo
from harborapi.models import Project
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


class ArtifactPanel(Widget):
    artifact = reactive(None, layout=True)  # type: Optional[ArtifactInfo]

    def render(self) -> Table:
        artifact = info.artifact
        table = Table(
            show_header=True,
            header_style="bold magenta",
            title=info.name_with_digest,
        )
        table.add_row("Architecture", artifact.architecture)

    def on_mount(self) -> None:
        self.render()


class ArtifactScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(ArtifactPanel())
        yield Footer()
