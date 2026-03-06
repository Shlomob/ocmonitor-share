"""Main TUI application for OpenCode Monitor."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import ContentSwitcher, Footer, Header

from ..config import Config, ModelPricing
from ..models.workflow import SessionWorkflow
from ..services.export_service import ExportService
from ..services.session_analyzer import SessionAnalyzer
from ..services.session_grouper import SessionGrouper
from ..utils.data_loader import DataLoader
from .widgets.breadcrumb import BreadcrumbBar
from .widgets.sidebar import Sidebar


class OCMonitorApp(App):
    """OpenCode Monitor TUI Application."""

    TITLE = "OpenCode Monitor"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("escape", "go_back", "Back", show=True),
        Binding("e", "export", "Export", show=True),
        Binding("t", "toggle_theme", "Theme", show=True),
        Binding("question_mark", "help", "Help", show=True),
        Binding("1", "switch_screen('sessions')", "Sessions", show=False),
        Binding("2", "switch_screen('daily')", "Daily", show=False),
        Binding("3", "switch_screen('weekly')", "Weekly", show=False),
        Binding("4", "switch_screen('monthly')", "Monthly", show=False),
        Binding("5", "switch_screen('models')", "Models", show=False),
        Binding("6", "switch_screen('projects')", "Projects", show=False),
        Binding("7", "switch_screen('live')", "Live", show=False),
        Binding("8", "switch_screen('config')", "Config", show=False),
    ]

    def __init__(
        self,
        config: Config,
        pricing_data: Dict[str, ModelPricing],
        no_remote: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.config = config
        self.pricing_data = pricing_data
        self.no_remote = no_remote
        self.analyzer: Optional[SessionAnalyzer] = None
        self.grouper: Optional[SessionGrouper] = None
        self.data_loader: Optional[DataLoader] = None
        self.export_service: Optional[ExportService] = None
        self._screen_stack_names: List[str] = []

    def on_mount(self) -> None:
        self.analyzer = SessionAnalyzer(self.pricing_data)
        self.grouper = SessionGrouper()
        self.data_loader = DataLoader(
            db_path=Path(self.config.paths.database_file),
            files_path=Path(self.config.paths.messages_dir),
        )
        self.export_service = ExportService(self.config.paths.export_dir)
        self.dark = self.config.ui.theme == "dark"
        self.switch_top_level("sessions")

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            yield Sidebar(id="sidebar")
            with Vertical(id="content-area"):
                yield BreadcrumbBar(id="breadcrumb")
                yield ContentSwitcher(id="content-switcher", initial=None)
        yield Footer()

    def switch_top_level(self, screen_name: str) -> None:
        """Switch the top-level content area to a different screen."""
        switcher = self.query_one("#content-switcher", ContentSwitcher)

        # Lazy-load screen widgets
        if not switcher.query(f"#{screen_name}"):
            widget = self._create_screen_widget(screen_name)
            if widget is None:
                self.notify(f"Unknown screen: {screen_name}", severity="error")
                return
            switcher.mount(widget)

        switcher.current = screen_name
        self._screen_stack_names = [screen_name]
        self.update_breadcrumb([self._screen_display_name(screen_name)])

        try:
            sidebar = self.query_one(Sidebar)
            sidebar.set_active(screen_name)
        except NoMatches:
            pass

    def _create_screen_widget(self, name: str):
        """Create a screen widget by name (lazy import)."""
        if name == "sessions":
            from .screens.sessions import SessionsPanel
            return SessionsPanel(id="sessions")
        elif name == "daily":
            from .screens.daily import DailyPanel
            return DailyPanel(id="daily")
        elif name == "weekly":
            from .screens.weekly import WeeklyPanel
            return WeeklyPanel(id="weekly")
        elif name == "monthly":
            from .screens.monthly import MonthlyPanel
            return MonthlyPanel(id="monthly")
        elif name == "models":
            from .screens.models import ModelsPanel
            return ModelsPanel(id="models")
        elif name == "projects":
            from .screens.projects import ProjectsPanel
            return ProjectsPanel(id="projects")
        elif name == "live":
            from .screens.live import LivePanel
            return LivePanel(id="live")
        elif name == "config":
            from .screens.config import ConfigPanel
            return ConfigPanel(id="config")
        return None

    def _screen_display_name(self, name: str) -> str:
        return {
            "sessions": "Sessions",
            "daily": "Daily",
            "weekly": "Weekly",
            "monthly": "Monthly",
            "models": "Models",
            "projects": "Projects",
            "live": "Live",
            "config": "Config",
        }.get(name, name.title())

    def update_breadcrumb(self, path: List[str]) -> None:
        try:
            bar = self.query_one("#breadcrumb", BreadcrumbBar)
            bar.path = path
        except NoMatches:
            pass

    def on_sidebar_navigate(self, message: Sidebar.Navigate) -> None:
        self.switch_top_level(message.screen_name)

    def action_switch_screen(self, screen_name: str) -> None:
        self.switch_top_level(screen_name)

    def action_go_back(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()
        elif len(self._screen_stack_names) > 1:
            self._screen_stack_names.pop()
            self.switch_top_level(self._screen_stack_names[-1])

    def action_toggle_theme(self) -> None:
        self.dark = not self.dark

    def action_export(self) -> None:
        from .widgets.export_modal import ExportModal
        self.push_screen(ExportModal())

    def action_help(self) -> None:
        from .screens.help import HelpScreen
        self.push_screen(HelpScreen())

    @staticmethod
    def adapt_hierarchy_to_workflows(hierarchy: dict) -> List[SessionWorkflow]:
        """Convert a session hierarchy dict to a sorted list of SessionWorkflow objects."""
        from datetime import datetime as _dt
        root_sessions = hierarchy.get("root_sessions", [])
        workflows = []
        for entry in root_sessions:
            session = entry.get("session")
            sub_agents = entry.get("sub_agents", [])
            if session:
                wf = SessionWorkflow(
                    workflow_id=session.session_id,
                    main_session=session,
                    sub_agent_sessions=sub_agents,
                )
                workflows.append(wf)
        return sorted(
            workflows,
            key=lambda w: w.start_time or _dt.min,
            reverse=True,
        )

    @staticmethod
    def resolve_timeframe_dates(
        timeframe: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> tuple[Optional[date], Optional[date]]:
        """Convert a timeframe label to concrete date bounds."""
        today = date.today()
        if timeframe == "daily":
            resolved_start = start_date or today
            resolved_end = end_date or today
        elif timeframe == "weekly":
            resolved_start = start_date or (today - timedelta(days=today.weekday()))
            resolved_end = end_date or (resolved_start + timedelta(days=6))
        elif timeframe == "monthly":
            resolved_start = start_date or today.replace(day=1)
            next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
            resolved_end = end_date or (next_month - timedelta(days=1))
        else:
            resolved_start = start_date
            resolved_end = end_date
        return resolved_start, resolved_end
