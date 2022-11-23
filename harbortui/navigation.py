from typing import Protocol

from textual.binding import Binding
from textual.containers import Grid
from textual.message import Message
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, Static

from .notifications import ErrorNotification


class Options(Grid):
    """A container that holds ProgramOption objects."""

    def on_mount(self) -> None:
        for child in self.children:
            child.add_class("option")

    def select(self, previous: bool = False) -> None:
        """Focuses the next or previous option in the list of options."""
        children = list(self.children)
        if not children:
            return

        for i, child in enumerate(children):
            if not self.screen.focused == child:
                continue
            if previous:
                next_child = children[i - 1]
            else:
                nxt = i + 1 if len(children) > i + 1 else 0
                next_child = children[nxt]
            self.screen.set_focus(next_child)
            break
        else:
            self.screen.set_focus(children[0])


class ProgramOption(Button):
    """A single option, usually contained in an Options container."""

    def render(self) -> str:
        return self.label

    # pass
    # async def on_click(self) -> None:
    #     await self.emit(self.Clicked(self))

    # def on_mouse_event(self) -> None:
    #     for child in self.children:
    #         if child.has_class("-active"):
    #             child.remove_class("-active")

    # class Clicked(Message, bubble=True):
    #     def __init__(self, sender: "ProgramOption") -> None:
    #         super().__init__(sender)


class Queryer(Protocol):
    screen: Screen
    query = Widget.query
    query_one = Widget.query_one


class NavigationMixin:
    BINDINGS = [
        Binding("up", "select_prev", "Previous Option", universal=True),
        ("down", "select_next", "Next Option"),
        ("enter", "select_option", "Select Option"),
    ]

    def action_select_prev(self: Queryer) -> None:
        """Selects the previous option in the current screen."""
        options = self.screen.query_one(Options)
        options.select(previous=True)

    def action_select_next(self: Queryer) -> None:
        """Selects the next option in the current screen."""
        options = self.screen.query_one(Options)
        options.select(previous=False)

    async def on_button_pressed(self, event: ProgramOption.Pressed) -> None:
        option_id = event.sender.id
        if option_id is None:
            return
        if not isinstance(event.sender, ProgramOption):
            return

        # Try to show the screen for the option
        if hasattr(self, "SCREENS") and option_id in self.SCREENS:
            self.push_screen(option_id)
        else:
            sender = event.sender
            option_name = sender.renderable or sender.label or option_id
            self.screen.mount(ErrorNotification(f"{option_name}: Not implemented yet"))
