"""Monthly breakdown screen."""

from typing import List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Label, Static

from ...models.analytics import MonthlyUsage
from ...utils.time_utils import TimeUtils


MONTH_NAMES = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


class MonthlyPanel(Static):
    """Panel showing monthly usage breakdown."""

    BINDINGS = [
        Binding("d", "toggle_breakdown", "Breakdown"),
        Binding("r", "refresh_data", "Refresh"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._monthly: List[MonthlyUsage] = []
        self._sessions = []
        self._show_breakdown = False

    def compose(self) -> ComposeResult:
        yield DataTable(id="monthly-table")
        yield Label("", id="monthly-summary", classes="summary-bar")

    def on_mount(self) -> None:
        table = self.query_one("#monthly-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        self._load_data()

    def _load_data(self) -> None:
        self.run_worker(self._fetch, thread=True)

    def _fetch(self) -> None:
        app = self.app
        self._sessions = app.analyzer.analyze_all_sessions()
        self._monthly = app.analyzer.create_monthly_breakdown(self._sessions)
        self.app.call_from_thread(self._update_view)

    def _update_view(self) -> None:
        table = self.query_one("#monthly-table", DataTable)
        table.clear(columns=True)
        app = self.app

        if self._show_breakdown:
            table.add_columns("Month", "Weeks", "Sessions", "Model", "Tokens", "Cost")
            for month in self._monthly:
                all_sessions = [
                    s
                    for w in month.weekly_usage
                    for d in w.daily_usage
                    for s in d.sessions
                ]
                breakdown = {}
                for s in all_sessions:
                    mb = s.get_model_breakdown(app.pricing_data)
                    for model, data in mb.items():
                        if model not in breakdown:
                            breakdown[model] = {"tokens": 0, "cost": 0}
                        tokens = data.get("tokens")
                        breakdown[model]["tokens"] += tokens.total if tokens else 0
                        breakdown[model]["cost"] += float(data.get("cost", 0))

                month_key = f"{month.year}-{month.month:02d}"
                month_label = f"{MONTH_NAMES[month.month]} {month.year}"
                first = True
                for model, data in breakdown.items():
                    row_key = month_key if first else f"{month_key}:{model}"
                    table.add_row(
                        month_label if first else "",
                        str(len(month.weekly_usage)) if first else "",
                        str(month.total_sessions) if first else "",
                        model[:30],
                        f"{data['tokens']:,}",
                        f"${data['cost']:.4f}",
                        key=row_key,
                    )
                    first = False
                if not breakdown:
                    cost = sum(
                        s.calculate_total_cost(app.pricing_data) for s in all_sessions
                    )
                    table.add_row(
                        month_label,
                        str(len(month.weekly_usage)),
                        str(month.total_sessions),
                        "-",
                        f"{month.total_tokens.total:,}",
                        f"${cost:.4f}",
                        key=month_key,
                    )
        else:
            table.add_columns("Month", "Weeks", "Sessions", "Interactions", "Tokens", "Cost")
            for month in self._monthly:
                all_sessions = [
                    s
                    for w in month.weekly_usage
                    for d in w.daily_usage
                    for s in d.sessions
                ]
                cost = sum(
                    s.calculate_total_cost(app.pricing_data) for s in all_sessions
                )
                month_key = f"{month.year}-{month.month:02d}"
                month_label = f"{MONTH_NAMES[month.month]} {month.year}"
                table.add_row(
                    month_label,
                    str(len(month.weekly_usage)),
                    str(month.total_sessions),
                    str(month.total_interactions),
                    f"{month.total_tokens.total:,}",
                    f"${cost:.4f}",
                    key=month_key,
                )

        self._update_summary()

    def _update_summary(self) -> None:
        app = self.app
        summary = app.analyzer.get_sessions_summary(self._sessions)
        label = self.query_one("#monthly-summary", Label)
        label.update(
            f"{len(self._monthly)} months | "
            f"{summary['total_sessions']} sessions | "
            f"{summary['total_tokens'].total:,} tokens | "
            f"${summary['total_cost']:.4f}"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        month_key = key.split(":")[0]
        try:
            parts = month_key.split("-")
            year, month_num = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return
        month = next(
            (m for m in self._monthly if m.year == year and m.month == month_num),
            None,
        )
        if month:
            self.app.push_screen(MonthlyDetailScreen(month))

    def action_toggle_breakdown(self) -> None:
        self._show_breakdown = not self._show_breakdown
        self._update_view()

    def action_refresh_data(self) -> None:
        self._load_data()

    def get_export_data(self):
        return ("monthly", {"monthly_usage": self._monthly})


class MonthlyDetailScreen(Screen):
    """Detail view for a single month's usage."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
    ]

    def __init__(self, month: MonthlyUsage, **kwargs) -> None:
        super().__init__(**kwargs)
        self._month = month

    def compose(self) -> ComposeResult:
        month_label = f"{MONTH_NAMES[self._month.month]} {self._month.year}"
        with VerticalScroll(classes="detail-panel"):
            yield Label(f"Monthly Detail: {month_label}", classes="detail-section-title")
            yield Static(id="month-info")
            yield Label("Weekly Breakdown", classes="detail-section-title")
            yield DataTable(id="month-weekly-table")

    def on_mount(self) -> None:
        app = self.app
        month = self._month
        cost = month.calculate_total_cost(app.pricing_data)
        info = (
            f"Month: {MONTH_NAMES[month.month]} {month.year}\n"
            f"Weeks: {len(month.weekly_usage)}  Sessions: {month.total_sessions}\n"
            f"Interactions: {month.total_interactions}  Tokens: {month.total_tokens.total:,}\n"
            f"Cost: ${cost:.4f}"
        )
        self.query_one("#month-info", Static).update(info)

        table = self.query_one("#month-weekly-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Week", "Days", "Sessions", "Tokens", "Cost")

        for week in month.weekly_usage:
            week_cost = week.calculate_total_cost(app.pricing_data)
            week_label = TimeUtils.format_week_range(week.start_date, week.end_date)
            table.add_row(
                week_label,
                str(len(week.daily_usage)),
                str(week.total_sessions),
                f"{week.total_tokens.total:,}",
                f"${week_cost:.4f}",
                key=week.start_date.isoformat(),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        from datetime import date as date_type
        try:
            target_date = date_type.fromisoformat(key)
        except ValueError:
            return
        week = next((w for w in self._month.weekly_usage if w.start_date == target_date), None)
        if week:
            from .weekly import WeeklyDetailScreen
            self.app.push_screen(WeeklyDetailScreen(week))

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
