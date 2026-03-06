"""Sessions screen for the TUI."""

from decimal import Decimal
from typing import List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static
from textual.worker import Worker, WorkerState

from ...models.session import SessionData
from ...models.workflow import SessionWorkflow
from ...utils.time_utils import TimeUtils
from ..widgets.filter_bar import FilterBar


class SessionsPanel(Static):
    """Panel showing all sessions with optional workflow grouping."""

    BINDINGS = [
        Binding("g", "toggle_grouped", "Group"),
        Binding("r", "refresh_data", "Refresh"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._sessions: List[SessionData] = []
        self._workflows: List[SessionWorkflow] = []
        self._grouped = True
        self._sort_key: Optional[str] = None
        self._sort_reverse = True
        self._model_filter: Optional[str] = None
        self._project_filter: Optional[str] = None
        self._limit: Optional[int] = None

    def compose(self) -> ComposeResult:
        yield FilterBar(
            filters=[
                {
                    "name": "model",
                    "label": "Model:",
                    "type": "input",
                    "placeholder": "filter by model",
                },
                {
                    "name": "project",
                    "label": "Project:",
                    "type": "input",
                    "placeholder": "filter by project",
                },
                {
                    "name": "limit",
                    "label": "Limit:",
                    "type": "input",
                    "placeholder": "e.g. 50",
                },
            ],
            id="sessions-filter",
        )
        yield DataTable(id="sessions-table")
        yield Label("", id="sessions-summary", classes="summary-bar")

    def on_mount(self) -> None:
        table = self.query_one("#sessions-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        self._setup_columns(table)
        self._load_data()

    def _setup_columns(self, table: DataTable) -> None:
        table.clear(columns=True)
        table.add_columns(
            "Started", "Duration", "Session", "Model", "Tokens", "Cost", "Agent"
        )

    def _load_data(self) -> None:
        self.run_worker(self._fetch_sessions, thread=True)

    def _fetch_sessions(self) -> None:
        app = self.app
        sessions = app.analyzer.analyze_all_sessions(limit=self._limit)

        if self._model_filter:
            sessions = app.analyzer.filter_sessions_by_model(
                sessions, [self._model_filter]
            )

        if self._project_filter:
            sessions = [s for s in sessions if self._project_filter.lower() in (s.project_name or "").lower()]

        self._sessions = sessions
        self._workflows = app.grouper.group_sessions(sessions)
        self.app.call_from_thread(self._render_table)

    def _render_table(self) -> None:
        table = self.query_one("#sessions-table", DataTable)
        table.clear()

        app = self.app

        if self._grouped and self._workflows:
            for wf in self._workflows:
                cost = wf.calculate_total_cost(app.pricing_data)
                tokens = wf.total_tokens
                started = (
                    wf.start_time.strftime("%Y-%m-%d %H:%M") if wf.start_time else "-"
                )
                main = wf.main_session
                duration = TimeUtils.format_duration(main.duration_ms) if main.duration_ms else "-"
                model = ", ".join(main.models_used[:2])
                if len(main.models_used) > 2:
                    model += "..."
                title = wf.display_title[:40]
                if wf.has_sub_agents:
                    title += f" (+{wf.sub_agent_count})"
                agent = main.agent or "-"
                table.add_row(
                    started,
                    duration,
                    title,
                    model,
                    f"{tokens.total:,}",
                    f"${cost:.4f}",
                    agent,
                    key=wf.workflow_id,
                )
        else:
            for s in self._sessions:
                cost = s.calculate_total_cost(app.pricing_data)
                tokens = s.total_tokens
                started = (
                    s.start_time.strftime("%Y-%m-%d %H:%M") if s.start_time else "-"
                )
                duration = TimeUtils.format_duration(s.duration_ms) if s.duration_ms else "-"
                model = ", ".join(s.models_used[:2])
                if len(s.models_used) > 2:
                    model += "..."
                title = s.display_title[:40]
                agent = s.agent or "-"
                table.add_row(
                    started,
                    duration,
                    title,
                    model,
                    f"{tokens.total:,}",
                    f"${cost:.4f}",
                    agent,
                    key=s.session_id,
                )

        self._update_summary()

    def _update_summary(self) -> None:
        app = self.app
        summary = app.analyzer.get_sessions_summary(self._sessions)
        total_cost = summary["total_cost"]
        label = self.query_one("#sessions-summary", Label)
        mode = "workflows" if self._grouped else "sessions"
        count = len(self._workflows) if self._grouped else len(self._sessions)
        label.update(
            f"{count} {mode} | "
            f"{summary['total_interactions']} interactions | "
            f"{summary['total_tokens'].total:,} tokens | "
            f"${total_cost:.4f} total"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        session = self._find_session(key)
        if session:
            from .session_detail import SessionDetailScreen
            self.app.push_screen(SessionDetailScreen(session))

    def _find_session(self, key: str) -> Optional[SessionData]:
        if self._grouped:
            for wf in self._workflows:
                if wf.workflow_id == key:
                    return wf.main_session
        for s in self._sessions:
            if s.session_id == key:
                return s
        return None

    def action_toggle_grouped(self) -> None:
        self._grouped = not self._grouped
        self._render_table()
        self.app.notify(
            f"{'Grouped' if self._grouped else 'Flat'} view"
        )

    def action_refresh_data(self) -> None:
        self._load_data()

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        if event.filter_name == "model":
            self._model_filter = event.value if event.value else None
        elif event.filter_name == "project":
            self._project_filter = event.value if event.value else None
        elif event.filter_name == "limit":
            try:
                self._limit = int(event.value) if event.value else None
            except ValueError:
                self._limit = None
        self._load_data()

    def get_export_data(self):
        return ("sessions", {"sessions": self._sessions})

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        # Simple column sort toggle
        col_label = str(event.label)
        if self._sort_key == col_label:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_key = col_label
            self._sort_reverse = True
        table = self.query_one("#sessions-table", DataTable)
        table.sort(event.column_key, reverse=self._sort_reverse)
