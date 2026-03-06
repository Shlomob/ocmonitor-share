"""Session detail screen (pushed on drill-down)."""

from decimal import Decimal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Label, Static

from ...models.session import SessionData
from ...utils.time_utils import TimeUtils


class SessionDetailScreen(Screen):
    """Detail view for a single session."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
    ]

    def __init__(self, session: SessionData, **kwargs) -> None:
        super().__init__(**kwargs)
        self.session = session

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="detail-panel"):
            yield Label("Session Detail", classes="detail-section-title")
            yield Static(id="session-info")
            yield Label("Model Breakdown", classes="detail-section-title")
            yield DataTable(id="model-breakdown-table")
            yield Label("Interactions", classes="detail-section-title")
            yield DataTable(id="interactions-table")
            yield Label("Tool Usage", classes="detail-section-title")
            yield DataTable(id="tool-usage-table")

    def on_mount(self) -> None:
        self._render_info()
        self._render_model_breakdown()
        self._render_interactions()
        self._render_tool_usage()

    def _render_info(self) -> None:
        s = self.session
        app = self.app
        cost = s.calculate_total_cost(app.pricing_data)
        tokens = s.total_tokens
        started = s.start_time.strftime("%Y-%m-%d %H:%M:%S") if s.start_time else "-"
        duration = TimeUtils.format_duration(s.duration_ms) if s.duration_ms else "-"

        # Quota progress
        quota_pct = s.duration_percentage
        quota_bar = self._progress_bar(quota_pct)

        info = (
            f"ID: {s.session_id}\n"
            f"Title: {s.display_title}\n"
            f"Project: {s.project_name}\n"
            f"Started: {started}  Duration: {duration}\n"
            f"Models: {', '.join(s.models_used)}\n"
            f"Interactions: {s.interaction_count}  Tokens: {tokens.total:,}  Cost: ${cost:.4f}\n"
            f"Quota: {quota_bar} {quota_pct:.0f}%"
        )
        self.query_one("#session-info", Static).update(info)

    def _render_model_breakdown(self) -> None:
        table = self.query_one("#model-breakdown-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Model", "Interactions", "Input", "Output", "Cache R", "Cache W", "Total", "Cost")

        breakdown = self.session.get_model_breakdown(self.app.pricing_data)
        for model, data in breakdown.items():
            tokens = data.get("tokens")
            table.add_row(
                model,
                str(data.get("files", 0)),
                f"{tokens.input:,}" if tokens else "0",
                f"{tokens.output:,}" if tokens else "0",
                f"{tokens.cache_read:,}" if tokens else "0",
                f"{tokens.cache_write:,}" if tokens else "0",
                f"{tokens.total:,}" if tokens else "0",
                f"${data.get('cost', Decimal(0)):.4f}",
            )

    def _render_interactions(self) -> None:
        table = self.query_one("#interactions-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Time", "Model", "Input", "Output", "Total", "Duration")

        for f in self.session.files:
            created = "-"
            if f.time_data and f.time_data.created_datetime:
                created = f.time_data.created_datetime.strftime("%H:%M:%S")
            dur = "-"
            if f.time_data and f.time_data.duration_ms:
                dur = TimeUtils.format_duration(f.time_data.duration_ms)
            table.add_row(
                created,
                f.model_id[:30],
                f"{f.tokens.input:,}",
                f"{f.tokens.output:,}",
                f"{f.tokens.total:,}",
                dur,
            )

    def _render_tool_usage(self) -> None:
        table = self.query_one("#tool-usage-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Tool", "Calls")

        tools = self.app.data_loader.load_tool_usage([self.session.session_id])
        if tools:
            for t in tools:
                table.add_row(t.tool_name, str(t.total_calls))
        else:
            table.add_row("(no tool usage data)", "-")

    def get_export_data(self):
        return ("single_session", {"session": self.session})

    @staticmethod
    def _progress_bar(pct: float, width: int = 20) -> str:
        filled = int(width * min(pct, 100) / 100)
        return "[" + "#" * filled + "-" * (width - filled) + "]"

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
