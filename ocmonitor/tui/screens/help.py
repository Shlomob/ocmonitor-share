"""Help overlay screen."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


HELP_TEXT = """\
Keybindings

  Navigation
    1-8        Switch to screen (Sessions/Daily/Weekly/Monthly/Models/Projects/Live/Config)
    Escape     Go back / dismiss
    Enter      Drill into selected row

  Screens
    g          Toggle grouped/flat view (Sessions)
    d          Toggle model breakdown (Daily/Weekly/Monthly)
    r          Refresh data

  Live Dashboard
    w          Pick workflow
    p          Pause/resume refresh
    f          Toggle fullscreen (hide sidebar)
    +/-        Adjust refresh interval

  Global
    q          Quit
    e          Export data
    t          Toggle dark/light theme
    ?          Show this help
"""


class HelpScreen(ModalScreen[None]):
    """Dismissible keybinding reference overlay."""

    BINDINGS = [
        Binding("escape", "dismiss_help", "Close"),
        Binding("question_mark", "dismiss_help", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Label("Help", classes="detail-section-title")
            yield Static(HELP_TEXT)
            yield Button("Close", variant="primary", id="help-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.dismiss(None)

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
