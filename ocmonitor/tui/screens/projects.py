"""Projects breakdown screen."""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Label, Static

from ...models.analytics import ProjectBreakdownReport, ProjectUsageStats
from ...models.session import SessionData
from ..widgets.filter_bar import FilterBar


class ProjectsPanel(Static):
    """Panel showing project usage breakdown."""

    BINDINGS = [
        Binding("r", "refresh_data", "Refresh"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._report: Optional[ProjectBreakdownReport] = None
        self._sessions = []
        self._timeframe = "all"
        self._start_date: Optional[date] = None
        self._end_date: Optional[date] = None

    def compose(self) -> ComposeResult:
        yield FilterBar(
            filters=[
                {
                    "name": "timeframe",
                    "label": "Timeframe:",
                    "type": "select",
                    "options": [
                        ("All Time", "all"),
                        ("Daily", "daily"),
                        ("Weekly", "weekly"),
                        ("Monthly", "monthly"),
                    ],
                },
                {
                    "name": "start_date",
                    "label": "From:",
                    "type": "input",
                    "placeholder": "YYYY-MM-DD",
                },
                {
                    "name": "end_date",
                    "label": "To:",
                    "type": "input",
                    "placeholder": "YYYY-MM-DD",
                },
            ],
            id="projects-filter",
        )
        yield DataTable(id="projects-table")
        yield Label("", id="projects-summary", classes="summary-bar")

    def on_mount(self) -> None:
        table = self.query_one("#projects-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        self._load_data()

    def _load_data(self) -> None:
        self.run_worker(self._fetch, thread=True)

    def _fetch(self) -> None:
        app = self.app
        self._sessions = app.analyzer.analyze_all_sessions()
        resolved_start, resolved_end = app.resolve_timeframe_dates(
            self._timeframe, self._start_date, self._end_date
        )
        self._report = app.analyzer.create_project_breakdown(
            self._sessions, self._timeframe, resolved_start, resolved_end
        )
        self.app.call_from_thread(self._update_view)

    def _update_view(self) -> None:
        table = self.query_one("#projects-table", DataTable)
        table.clear(columns=True)
        table.add_columns(
            "Project", "Sessions", "Interactions", "Tokens", "Cost", "Models", "Last Activity"
        )

        if not self._report:
            return

        for p in self._report.project_stats:
            last_activity = (
                p.last_activity.strftime("%Y-%m-%d") if p.last_activity else "-"
            )
            table.add_row(
                p.project_name[:30],
                str(p.total_sessions),
                str(p.total_interactions),
                f"{p.total_tokens.total:,}",
                f"${p.total_cost:.4f}",
                ", ".join(p.models_used[:3]),
                last_activity,
                key=p.project_name,
            )

        self._update_summary()

    def _update_summary(self) -> None:
        if not self._report:
            return
        label = self.query_one("#projects-summary", Label)
        label.update(
            f"{len(self._report.project_stats)} projects | "
            f"{sum(p.total_sessions for p in self._report.project_stats)} sessions | "
            f"{self._report.total_tokens.total:,} tokens | "
            f"${self._report.total_cost:.4f}"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        project_name = str(event.row_key.value)
        if not project_name or not self._report:
            return
        stats = next(
            (p for p in self._report.project_stats if p.project_name == project_name),
            None,
        )
        sessions = [
            s for s in self._sessions
            if (s.project_name or "Unknown") == project_name
        ]
        self.app.push_screen(ProjectDetailScreen(project_name, stats, sessions))

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        if event.filter_name == "timeframe":
            self._timeframe = event.value
        elif event.filter_name == "start_date":
            try:
                self._start_date = date.fromisoformat(event.value) if event.value else None
            except ValueError:
                self._start_date = None
        elif event.filter_name == "end_date":
            try:
                self._end_date = date.fromisoformat(event.value) if event.value else None
            except ValueError:
                self._end_date = None
        self._load_data()

    def action_refresh_data(self) -> None:
        self._load_data()

    def get_export_data(self):
        return ("projects", {"project_breakdown": self._report})


class ProjectDetailScreen(Screen):
    """Detail view for a single project."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
    ]

    def __init__(
        self,
        project_name: str,
        stats: Optional[ProjectUsageStats] = None,
        sessions: Optional[List[SessionData]] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._project_name = project_name
        self._stats = stats
        self._sessions = sessions or []

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="detail-panel"):
            yield Label(f"Project: {self._project_name}", classes="detail-section-title")
            yield Static(id="project-info")
            yield Label("Sessions", classes="detail-section-title")
            yield DataTable(id="project-sessions-table")

    def on_mount(self) -> None:
        app = self.app

        info_widget = self.query_one("#project-info", Static)
        if self._stats:
            s = self._stats
            info_widget.update(
                f"Project: {s.project_name}\n"
                f"Sessions: {s.total_sessions}  Interactions: {s.total_interactions}\n"
                f"Tokens: {s.total_tokens.total:,}  Cost: ${s.total_cost:.4f}\n"
                f"Models: {', '.join(s.models_used)}"
            )
        else:
            info_widget.update(f"Project: {self._project_name}\nNo stats available")

        table = self.query_one("#project-sessions-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Started", "Session", "Model", "Tokens", "Cost")

        for sess in self._sessions:
            cost = sess.calculate_total_cost(app.pricing_data)
            started = sess.start_time.strftime("%Y-%m-%d %H:%M") if sess.start_time else "-"
            model = ", ".join(sess.models_used[:2])
            if len(sess.models_used) > 2:
                model += "..."
            table.add_row(
                started,
                sess.display_title[:35],
                model,
                f"{sess.total_tokens.total:,}",
                f"${cost:.4f}",
                key=sess.session_id,
            )
        if not self._sessions:
            table.add_row("(no sessions)", "-", "-", "-", "-")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        session_id = str(event.row_key.value)
        session = next((s for s in self._sessions if s.session_id == session_id), None)
        if session:
            from .session_detail import SessionDetailScreen
            self.app.push_screen(SessionDetailScreen(session))

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
