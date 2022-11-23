import asyncio
import os
from typing import Optional, TypedDict

from harborapi import HarborAsyncClient
from harborapi.ext.api import get_artifacts
from httpx._config import Timeout
from textual.app import App, ComposeResult
from textual.containers import Container, Grid
from textual.message import Message
from textual.widgets import Button, Footer, Header, Static, TextLog

from . import harbor
from .config import HarborTUIConfig, init_config_dir, load_config
from .navigation import NavigationMixin, Options, ProgramOption
from .notifications import (
    AutoremoveNotification,
    CenterNotification,
    ErrorNotification,
    Notification,
)
from .screens.login import LoginScreen
from .screens.projects import ProjectsScreen

config: Optional[HarborTUIConfig] = None


def setup() -> None:
    global config
    init_config_dir()
    config = load_config()


class HarborApp(App, NavigationMixin):
    # Textual app config
    CSS_PATH = "harbortui.scss"
    TITLE = "Harbor Browser"
    BINDINGS = [
        ("up", "select_prev", "Previous Option"),
        ("down", "select_next", "Next Option"),
        ("enter", "select_option", "Select Option"),
        ("f1", "app.toggle_class('TextLog', '-hidden')", "Toggle Debug Log"),
    ]
    SCREENS = {
        "login": LoginScreen(id="login-screen"),
        "projects": ProjectsScreen(id="projects-screen"),
    }

    # State
    auth_failed = False
    """The last attempt to authenticate with the Harbor API failed."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        setup()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Options(
                ProgramOption("Projects", id="projects"),
                ProgramOption("Repositories", id="repositories"),
                ProgramOption("Artifacts", id="artifacts"),
                ProgramOption("Tags", id="tags"),
            ),
            TextLog(
                id="debug-log",
                classes="-hidden",
                wrap=False,
                highlight=True,
                markup=True,
            ),
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Loads config and initializes the Harbor API client."""
        await self.init_harbor_client()

    async def on_login_screen_complete(self, message: LoginScreen.Complete) -> None:
        global config
        if config is None:
            config = HarborTUIConfig(
                harbor=message.credentials,
            )
        else:
            config.harbor.url = message.credentials["url"]
            config.harbor.username = message.credentials["username"]
            config.harbor.secret = message.credentials["secret"]
        try:
            self.auth_failed = False
            await self.init_harbor_client()
        finally:
            self.pop_screen()

    async def init_harbor_client(self) -> None:
        # If we can't authenticate with config, prompt for credentials
        if config is None or not config.harbor.can_authenticate or self.auth_failed:
            self.push_screen("login")
            return

        client = HarborAsyncClient(**config.harbor.credentials)

        try:
            orig_timeout = client.client.timeout
            client.client._timeout = Timeout(5.0)
            self.screen.mount(AutoremoveNotification("Authenticating..."))
            # self.screen.mount(
            #     ErrorNotification("Logging in...")
            # )  # FIXME: This is not working
            await client.ping_harbor_api()
        except Exception as e:
            self.screen.mount(ErrorNotification("Login failed"))
            self.auth_failed = True
            return await self.init_harbor_client()  # FIXME: don't recurse
        else:
            client.client._timeout = orig_timeout
            self.screen.mount(AutoremoveNotification("Logged in"))
            harbor.init_client(client, app)


app = HarborApp()


if __name__ == "__main__":
    app.run()
