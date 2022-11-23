from textual.css.scalar import ScalarOffset
from textual.widgets import Static


class Notification(Static):
    def on_mount(self) -> None:
        self.add_class("notification")


class AutoremoveNotification(Notification):
    def on_mount(self) -> None:
        super().on_mount()
        self.set_timer(3, self.remove)


class ErrorNotification(Notification):
    def on_mount(self) -> None:
        super().on_mount()
        self.styles.background = "red"
        self.styles.animate("opacity", 0.0, delay=2, duration=1)
        self.set_timer(3, self.remove)

    def on_click(self) -> None:
        self.remove()


class CenterNotification(Notification):
    pass
