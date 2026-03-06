"""Models breakdown screen."""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Label, Static

from ...models.analytics import ModelBreakdownReport, ModelUsageStats
from ..widgets.filter_bar import FilterBar


class ModelsPanel(Static):
    """Panel showing model usage breakdown."""

    BINDINGS = [
        Binding("r", "refresh_data", "Refresh"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._report: Optional[ModelBreakdownReport] = None
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
            id="models-filter",
        )
        yield DataTable(id="models-table")
        yield Label("", id="models-summary", classes="summary-bar")

    def on_mount(self) -> None:
        table = self.query_one("#models-table", DataTable)
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
        self._report = app.analyzer.create_model_breakdown(
            self._sessions, self._timeframe, resolved_start, resolved_end
        )
        self.app.call_from_thread(self._update_view)

    def _update_view(self) -> None:
        table = self.query_one("#models-table", DataTable)
        table.clear(columns=True)
        table.add_columns(
            "Model", "Sessions", "Interactions", "Input", "Output", "Total", "Cost", "Cost%", "Speed"
        )

        if not self._report:
            return

        total_cost = self._report.total_cost or Decimal("0.0001")

        for m in self._report.model_stats:
            cost_pct = (
                f"{(m.total_cost / total_cost * 100):.1f}%"
                if total_cost
                else "0%"
            )
            speed = f"{m.p50_output_rate:.0f} tok/s" if m.p50_output_rate > 0 else "-"
            table.add_row(
                m.model_name[:30],
                str(m.total_sessions),
                str(m.total_interactions),
                f"{m.total_tokens.input:,}",
                f"{m.total_tokens.output:,}",
                f"{m.total_tokens.total:,}",
                f"${m.total_cost:.4f}",
                cost_pct,
                speed,
                key=m.model_name,
            )

        self._update_summary()

    def _update_summary(self) -> None:
        if not self._report:
            return
        label = self.query_one("#models-summary", Label)
        label.update(
            f"{len(self._report.model_stats)} models | "
            f"{sum(m.total_sessions for m in self._report.model_stats)} sessions | "
            f"{self._report.total_tokens.total:,} tokens | "
            f"${self._report.total_cost:.4f}"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        model_name = str(event.row_key.value)
        if model_name and self._report:
            stats = next(
                (m for m in self._report.model_stats if m.model_name == model_name),
                None,
            )
            sessions = [
                s for s in self._sessions
                if model_name in s.models_used
            ]
            self.app.push_screen(ModelDetailScreen(model_name, stats, sessions))

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
        return ("models", {"model_breakdown": self._report})


class ModelDetailScreen(Screen):
    """Detail view for a single model."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
    ]

    def __init__(
        self,
        model_name: str,
        stats: Optional[ModelUsageStats] = None,
        sessions: Optional[list] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.model_name = model_name
        self._stats = stats
        self._sessions = sessions or []

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="detail-panel"):
            yield Label("Model Detail", classes="detail-section-title")
            yield Static(id="model-info")
            yield Label("Sessions Using This Model", classes="detail-section-title")
            yield DataTable(id="model-sessions-table")
            yield Label("Tool Usage", classes="detail-section-title")
            yield DataTable(id="model-tool-table")

    def on_mount(self) -> None:
        try:
            self._update_view()
        except Exception as e:
            self.app.notify(f"Error loading model detail: {e}", severity="error")

    def _update_view(self) -> None:
        info_widget = self.query_one("#model-info", Static)
        app = self.app

        if self._stats:
            s = self._stats
            info_widget.update(
                f"Model: {s.model_name}\n"
                f"Sessions: {s.total_sessions}  Interactions: {s.total_interactions}\n"
                f"Tokens: {s.total_tokens.total:,}  Cost: ${s.total_cost:.4f}\n"
                f"Speed (p50): {s.p50_output_rate:.0f} tok/s"
            )
        else:
            info_widget.update(f"Model: {self.model_name}\nNo stats available")

        # Sessions table
        sessions_table = self.query_one("#model-sessions-table", DataTable)
        sessions_table.cursor_type = "row"
        sessions_table.zebra_stripes = True
        sessions_table.add_columns("Session", "Started", "Tokens", "Cost")

        for sess in self._sessions:
            cost = sess.calculate_total_cost(app.pricing_data)
            started = sess.start_time.strftime("%Y-%m-%d %H:%M") if sess.start_time else "-"
            sessions_table.add_row(
                sess.display_title[:35],
                started,
                f"{sess.total_tokens.total:,}",
                f"${cost:.4f}",
            )
        if not self._sessions:
            sessions_table.add_row("(no sessions)", "-", "-", "-")

        # Tool usage
        tool_table = self.query_one("#model-tool-table", DataTable)
        tool_table.cursor_type = "row"
        tool_table.zebra_stripes = True
        tool_table.add_columns("Tool", "Calls")

        session_ids = [s.session_id for s in self._sessions]
        tools = app.data_loader.load_tool_usage(session_ids) if session_ids else []
        if tools:
            for t in tools:
                tool_table.add_row(t.tool_name, str(t.total_calls))
        else:
            tool_table.add_row("(no tool usage data)", "-")

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
