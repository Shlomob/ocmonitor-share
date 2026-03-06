"""Navigation sidebar widget."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static


class SidebarItem(Static):
    """A clickable sidebar navigation item."""

    class Clicked(Message):
        def __init__(self, screen_name: str) -> None:
            self.screen_name = screen_name
            super().__init__()

    def __init__(self, label: str, screen_name: str, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self.screen_name = screen_name

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.screen_name))


class Sidebar(Widget):
    """Navigation sidebar with grouped menu items."""

    active_item: reactive[str] = reactive("sessions")

    class Navigate(Message):
        def __init__(self, screen_name: str) -> None:
            self.screen_name = screen_name
            super().__init__()

    NAV_GROUPS = [
        ("Analytics", [
            ("Sessions", "sessions"),
            ("Daily", "daily"),
            ("Weekly", "weekly"),
            ("Monthly", "monthly"),
        ]),
        ("Breakdown", [
            ("Models", "models"),
            ("Projects", "projects"),
        ]),
        ("Monitor", [
            ("Live", "live"),
        ]),
        ("System", [
            ("Config", "config"),
        ]),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar-nav"):
            yield Label("OpenCode Monitor", id="sidebar-title")
            for group_name, items in self.NAV_GROUPS:
                yield Label(group_name, classes="sidebar-group-label")
                for label, screen_name in items:
                    yield SidebarItem(
                        f"  {label}",
                        screen_name,
                        classes="sidebar-item",
                        id=f"nav-{screen_name}",
                    )

    def set_active(self, screen_name: str) -> None:
        self.active_item = screen_name

    def watch_active_item(self, old_value: str, new_value: str) -> None:
        for item in self.query(SidebarItem):
            item.remove_class("active")
            if item.screen_name == new_value:
                item.add_class("active")

    def on_sidebar_item_clicked(self, message: SidebarItem.Clicked) -> None:
        self.post_message(self.Navigate(message.screen_name))
