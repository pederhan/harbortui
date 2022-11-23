from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Footer, Header


class BaseScreen(Screen):
    # app.pop_screen or just pop_screen?
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        debug_log = self.app.query_one("#debug-log")
        yield debug_log
        yield Header()
        yield Footer()

    # def action_pop_screen(self) -> None:
    #     self.parent.pop_screen()
