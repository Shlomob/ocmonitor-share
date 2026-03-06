"""Daily breakdown screen."""

from datetime import date as date_type
from typing import List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Label, Static

from ...models.analytics import DailyUsage
from ...utils.time_utils import TimeUtils


class DailyPanel(Static):
    """Panel showing daily usage breakdown."""

    BINDINGS = [
        Binding("d", "toggle_breakdown", "Breakdown"),
        Binding("r", "refresh_data", "Refresh"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._daily: List[DailyUsage] = []
        self._sessions = []
        self._show_breakdown = False

    def compose(self) -> ComposeResult:
        yield DataTable(id="daily-table")
        yield Label("", id="daily-summary", classes="summary-bar")

    def on_mount(self) -> None:
        table = self.query_one("#daily-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        self._load_data()

    def _load_data(self) -> None:
        self.run_worker(self._fetch, thread=True)

    def _fetch(self) -> None:
        app = self.app
        self._sessions = app.analyzer.analyze_all_sessions()
        self._daily = app.analyzer.create_daily_breakdown(self._sessions)
        self.app.call_from_thread(self._update_view)

    def _update_view(self) -> None:
        table = self.query_one("#daily-table", DataTable)
        table.clear(columns=True)
        app = self.app

        if self._show_breakdown:
            table.add_columns("Date", "Sessions", "Interactions", "Model", "Tokens", "Cost")
            for day in self._daily:
                breakdown = {}
                for s in day.sessions:
                    mb = s.get_model_breakdown(app.pricing_data)
                    for model, data in mb.items():
                        if model not in breakdown:
                            breakdown[model] = {"tokens": 0, "cost": 0}
                        tokens = data.get("tokens")
                        breakdown[model]["tokens"] += tokens.total if tokens else 0
                        breakdown[model]["cost"] += float(data.get("cost", 0))

                first = True
                for model, data in breakdown.items():
                    row_key = day.date.isoformat() if first else f"{day.date.isoformat()}:{model}"
                    table.add_row(
                        day.date.strftime("%Y-%m-%d") if first else "",
                        str(len(day.sessions)) if first else "",
                        str(day.total_interactions) if first else "",
                        model[:30],
                        f"{data['tokens']:,}",
                        f"${data['cost']:.4f}",
                        key=row_key,
                    )
                    first = False
                if not breakdown:
                    cost = sum(s.calculate_total_cost(app.pricing_data) for s in day.sessions)
                    table.add_row(
                        day.date.strftime("%Y-%m-%d"),
                        str(len(day.sessions)),
                        str(day.total_interactions),
                        "-",
                        f"{day.total_tokens.total:,}",
                        f"${cost:.4f}",
                        key=day.date.isoformat(),
                    )
        else:
            table.add_columns("Date", "Sessions", "Interactions", "Tokens", "Cost", "Models")
            for day in self._daily:
                cost = sum(s.calculate_total_cost(app.pricing_data) for s in day.sessions)
                table.add_row(
                    day.date.strftime("%Y-%m-%d"),
                    str(len(day.sessions)),
                    str(day.total_interactions),
                    f"{day.total_tokens.total:,}",
                    f"${cost:.4f}",
                    ", ".join(day.models_used[:3]),
                    key=day.date.isoformat(),
                )

        self._update_summary()

    def _update_summary(self) -> None:
        app = self.app
        summary = app.analyzer.get_sessions_summary(self._sessions)
        label = self.query_one("#daily-summary", Label)
        label.update(
            f"{len(self._daily)} days | "
            f"{summary['total_sessions']} sessions | "
            f"{summary['total_tokens'].total:,} tokens | "
            f"${summary['total_cost']:.4f}"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        date_str = key.split(":")[0]
        try:
            target_date = date_type.fromisoformat(date_str)
        except ValueError:
            return
        day = next((d for d in self._daily if d.date == target_date), None)
        if day:
            self.app.push_screen(DailyDetailScreen(day))

    def action_toggle_breakdown(self) -> None:
        self._show_breakdown = not self._show_breakdown
        self._update_view()

    def action_refresh_data(self) -> None:
        self._load_data()

    def get_export_data(self):
        return ("daily", {"daily_usage": self._daily})


class DailyDetailScreen(Screen):
    """Detail view for a single day's usage."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
    ]

    def __init__(self, day: DailyUsage, **kwargs) -> None:
        super().__init__(**kwargs)
        self._day = day

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="detail-panel"):
            yield Label(f"Daily Detail: {self._day.date}", classes="detail-section-title")
            yield Static(id="day-info")
            yield Label("Sessions", classes="detail-section-title")
            yield DataTable(id="day-sessions-table")

    def on_mount(self) -> None:
        app = self.app
        day = self._day
        cost = day.calculate_total_cost(app.pricing_data)
        info = (
            f"Date: {day.date}\n"
            f"Sessions: {len(day.sessions)}  Interactions: {day.total_interactions}\n"
            f"Tokens: {day.total_tokens.total:,}  Cost: ${cost:.4f}\n"
            f"Models: {', '.join(day.models_used)}"
        )
        self.query_one("#day-info", Static).update(info)

        table = self.query_one("#day-sessions-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Started", "Session", "Model", "Tokens", "Cost")

        for s in day.sessions:
            s_cost = s.calculate_total_cost(app.pricing_data)
            started = s.start_time.strftime("%H:%M") if s.start_time else "-"
            model = ", ".join(s.models_used[:2])
            if len(s.models_used) > 2:
                model += "..."
            table.add_row(
                started,
                s.display_title[:35],
                model,
                f"{s.total_tokens.total:,}",
                f"${s_cost:.4f}",
                key=s.session_id,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        session_id = str(event.row_key.value)
        session = next((s for s in self._day.sessions if s.session_id == session_id), None)
        if session:
            from .session_detail import SessionDetailScreen
            self.app.push_screen(SessionDetailScreen(session))

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
