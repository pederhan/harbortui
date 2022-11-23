from typing import TypedDict

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from ..notifications import ErrorNotification
from .base import BaseScreen


class Credentials(TypedDict):
    url: str
    username: str
    secret: str


class LoginForm(Container):
    # FIXME: enter key should submit form
    url = reactive("")
    username = reactive("")
    password = reactive("")

    def compose(self) -> ComposeResult:
        yield Static("Harbor API URL", classes="label")
        yield Input(placeholder="URL", id="url")
        yield Static("Username", classes="label")
        yield Input(placeholder="Username", id="username")
        yield Static("Password", classes="label")
        yield Input(placeholder="Password", password=True, id="password")
        yield Static()
        yield Button("Login", id="login", variant="primary")

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "url":
            self.url = event.input.value
        elif event.input.id == "username":
            self.username = event.input.value
        elif event.input.id == "password":
            self.password = event.input.value

    async def on_key(self, event: Key) -> None:
        if event.key == "enter":
            await self.submit()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        await self.submit()

    async def submit(self) -> None:
        credentials = Credentials(
            url=self.url,
            username=self.username,
            secret=self.password,
        )
        await self.emit(
            LoginForm.Updated(
                self,
                credentials,
            )
        )

    class Updated(Message, bubble=True):
        def __init__(self, sender: "LoginForm", value: Credentials) -> None:
            super().__init__(sender)
            self.value = value


class LoginScreen(BaseScreen):
    def compose(self) -> ComposeResult:
        yield Container(LoginForm())

    async def on_login_form_updated(self, event: LoginForm.Updated) -> None:
        if event.value:
            if not all(v for v in event.value.values()):
                self.screen.mount(ErrorNotification("Please fill in all fields"))
                return
        await self.emit(LoginScreen.Complete(self, event.value))

    class Complete(Message, bubble=True):
        def __init__(self, sender: "LoginScreen", credentials: Credentials) -> None:
            super().__init__(sender)
            self.credentials = credentials
