"""Weekly breakdown screen."""

from datetime import date as date_type
from typing import List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Label, Static

from ...models.analytics import WeeklyUsage
from ...utils.time_utils import WEEKDAY_MAP, TimeUtils
from ..widgets.filter_bar import FilterBar


class WeeklyPanel(Static):
    """Panel showing weekly usage breakdown."""

    BINDINGS = [
        Binding("d", "toggle_breakdown", "Breakdown"),
        Binding("r", "refresh_data", "Refresh"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._weekly: List[WeeklyUsage] = []
        self._sessions = []
        self._show_breakdown = False
        self._week_start_day = 0  # Monday

    def compose(self) -> ComposeResult:
        day_options = [(name.title(), str(val)) for name, val in WEEKDAY_MAP.items()]
        yield FilterBar(
            filters=[
                {
                    "name": "week_start",
                    "label": "Week starts:",
                    "type": "select",
                    "options": day_options,
                },
            ],
            id="weekly-filter",
        )
        yield DataTable(id="weekly-table")
        yield Label("", id="weekly-summary", classes="summary-bar")

    def on_mount(self) -> None:
        table = self.query_one("#weekly-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        self._load_data()

    def _load_data(self) -> None:
        self.run_worker(self._fetch, thread=True)

    def _fetch(self) -> None:
        app = self.app
        self._sessions = app.analyzer.analyze_all_sessions()
        self._weekly = app.analyzer.create_weekly_breakdown(
            self._sessions, self._week_start_day
        )
        self.app.call_from_thread(self._update_view)

    def _update_view(self) -> None:
        table = self.query_one("#weekly-table", DataTable)
        table.clear(columns=True)
        app = self.app

        if self._show_breakdown:
            table.add_columns("Week", "Sessions", "Interactions", "Model", "Tokens", "Cost")
            for week in self._weekly:
                all_sessions = [s for d in week.daily_usage for s in d.sessions]
                breakdown = {}
                for s in all_sessions:
                    mb = s.get_model_breakdown(app.pricing_data)
                    for model, data in mb.items():
                        if model not in breakdown:
                            breakdown[model] = {"tokens": 0, "cost": 0}
                        tokens = data.get("tokens")
                        breakdown[model]["tokens"] += tokens.total if tokens else 0
                        breakdown[model]["cost"] += float(data.get("cost", 0))

                week_label = TimeUtils.format_week_range(week.start_date, week.end_date)
                first = True
                for model, data in breakdown.items():
                    row_key = week.start_date.isoformat() if first else f"{week.start_date.isoformat()}:{model}"
                    table.add_row(
                        week_label if first else "",
                        str(week.total_sessions) if first else "",
                        str(week.total_interactions) if first else "",
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
                        week_label,
                        str(week.total_sessions),
                        str(week.total_interactions),
                        "-",
                        f"{week.total_tokens.total:,}",
                        f"${cost:.4f}",
                        key=week.start_date.isoformat(),
                    )
        else:
            table.add_columns("Week", "Days", "Sessions", "Interactions", "Tokens", "Cost")
            for week in self._weekly:
                all_sessions = [s for d in week.daily_usage for s in d.sessions]
                cost = sum(s.calculate_total_cost(app.pricing_data) for s in all_sessions)
                week_label = TimeUtils.format_week_range(week.start_date, week.end_date)
                table.add_row(
                    week_label,
                    str(len(week.daily_usage)),
                    str(week.total_sessions),
                    str(week.total_interactions),
                    f"{week.total_tokens.total:,}",
                    f"${cost:.4f}",
                    key=week.start_date.isoformat(),
                )

        self._update_summary()

    def _update_summary(self) -> None:
        app = self.app
        summary = app.analyzer.get_sessions_summary(self._sessions)
        label = self.query_one("#weekly-summary", Label)
        label.update(
            f"{len(self._weekly)} weeks | "
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
        week = next((w for w in self._weekly if w.start_date == target_date), None)
        if week:
            self.app.push_screen(WeeklyDetailScreen(week))

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        if event.filter_name == "week_start":
            try:
                self._week_start_day = int(event.value)
            except ValueError:
                self._week_start_day = 0
            self._load_data()

    def action_toggle_breakdown(self) -> None:
        self._show_breakdown = not self._show_breakdown
        self._update_view()

    def action_refresh_data(self) -> None:
        self._load_data()

    def get_export_data(self):
        return ("weekly", {"weekly_usage": self._weekly})


class WeeklyDetailScreen(Screen):
    """Detail view for a single week's usage."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
    ]

    def __init__(self, week: WeeklyUsage, **kwargs) -> None:
        super().__init__(**kwargs)
        self._week = week

    def compose(self) -> ComposeResult:
        week_label = TimeUtils.format_week_range(self._week.start_date, self._week.end_date)
        with VerticalScroll(classes="detail-panel"):
            yield Label(f"Weekly Detail: {week_label}", classes="detail-section-title")
            yield Static(id="week-info")
            yield Label("Daily Breakdown", classes="detail-section-title")
            yield DataTable(id="week-daily-table")

    def on_mount(self) -> None:
        app = self.app
        week = self._week
        cost = week.calculate_total_cost(app.pricing_data)
        info = (
            f"Week: {TimeUtils.format_week_range(week.start_date, week.end_date)}\n"
            f"Sessions: {week.total_sessions}  Interactions: {week.total_interactions}\n"
            f"Tokens: {week.total_tokens.total:,}  Cost: ${cost:.4f}"
        )
        self.query_one("#week-info", Static).update(info)

        table = self.query_one("#week-daily-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Date", "Sessions", "Interactions", "Tokens", "Cost")

        for day in week.daily_usage:
            day_cost = day.calculate_total_cost(app.pricing_data)
            table.add_row(
                day.date.strftime("%Y-%m-%d"),
                str(len(day.sessions)),
                str(day.total_interactions),
                f"{day.total_tokens.total:,}",
                f"${day_cost:.4f}",
                key=day.date.isoformat(),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        try:
            target_date = date_type.fromisoformat(key)
        except ValueError:
            return
        day = next((d for d in self._week.daily_usage if d.date == target_date), None)
        if day:
            self.app.push_screen(DailyDetailScreen(day))

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
