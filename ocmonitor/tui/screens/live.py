"""Live dashboard screen."""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Button, DataTable, Label, OptionList, Static

from ...models.session import SessionData
from ...models.workflow import SessionWorkflow
from ...services.session_grouper import SessionGrouper
from ...utils.time_utils import TimeUtils


class LivePanel(Static):
    """Live monitoring dashboard with auto-refresh."""

    BINDINGS = [
        Binding("w", "pick_workflow", "Workflow"),
        Binding("p", "toggle_pause", "Pause"),
        Binding("f", "toggle_fullscreen", "Fullscreen"),
        Binding("plus", "increase_interval", "+Interval"),
        Binding("minus", "decrease_interval", "-Interval"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._timer: Optional[Timer] = None
        self._paused = False
        self._interval = 5
        self._workflow: Optional[SessionWorkflow] = None
        self._workflows: List[SessionWorkflow] = []
        self._hierarchy: Dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        yield Static("Live Dashboard", id="live-title", classes="live-header")
        with Horizontal(classes="live-metrics"):
            yield Static("", id="live-tokens", classes="metric-box")
            yield Static("", id="live-cost", classes="metric-box")
            yield Static("", id="live-speed", classes="metric-box")
            yield Static("", id="live-duration", classes="metric-box")
        yield Label("Model Usage", classes="detail-section-title")
        yield DataTable(id="live-model-table")
        yield Label("Sub-Agents", classes="detail-section-title")
        yield DataTable(id="live-subagent-table")
        yield Label("Tool Usage", classes="detail-section-title")
        yield DataTable(id="live-tool-table")
        yield Label("", id="live-status", classes="summary-bar")

    def on_mount(self) -> None:
        app = self.app
        self._interval = app.config.ui.live_refresh_interval

        # Setup tables
        model_table = self.query_one("#live-model-table", DataTable)
        model_table.cursor_type = "row"
        model_table.zebra_stripes = True

        subagent_table = self.query_one("#live-subagent-table", DataTable)
        subagent_table.cursor_type = "row"
        subagent_table.zebra_stripes = True

        tool_table = self.query_one("#live-tool-table", DataTable)
        tool_table.cursor_type = "row"
        tool_table.zebra_stripes = True

        self._refresh_data()
        self._timer = self.set_interval(self._interval, self._refresh_data)

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def _refresh_data(self) -> None:
        if self._paused:
            return
        self.run_worker(self._fetch, thread=True)

    def _fetch(self) -> None:
        app = self.app
        try:
            self._hierarchy = app.data_loader.load_session_hierarchy()
        except Exception:
            self._hierarchy = {"root_sessions": [], "all_sessions": [], "source": "none"}

        # Build workflows from hierarchy
        self._workflows = app.adapt_hierarchy_to_workflows(self._hierarchy)

        # Auto-select most recent workflow if none selected
        if not self._workflow and self._workflows:
            self._workflow = self._workflows[0]
        elif self._workflow and self._workflows:
            # Refresh current workflow data
            for wf in self._workflows:
                if wf.workflow_id == self._workflow.workflow_id:
                    self._workflow = wf
                    break

        self.app.call_from_thread(self._update_view)

    def _update_view(self) -> None:
        app = self.app
        wf = self._workflow

        # Title
        title = self.query_one("#live-title", Static)
        if wf:
            title.update(
                f"Live: {wf.display_title[:50]} | "
                f"{'PAUSED' if self._paused else 'LIVE'} | "
                f"Refresh: {self._interval}s"
            )
        else:
            title.update("Live Dashboard - No active workflow")
            return

        # Metrics
        tokens = wf.total_tokens
        cost = wf.calculate_total_cost(app.pricing_data)
        main = wf.main_session
        duration = TimeUtils.format_duration(main.duration_ms) if main.duration_ms else "-"

        # Compute output speed from eligible interactions
        output_rates = []
        for f in main.files:
            if f.is_rate_eligible and f.time_data and f.time_data.duration_ms and f.time_data.duration_ms > 0:
                rate = f.tokens.output / (f.time_data.duration_ms / 1000)
                output_rates.append(rate)
        p50_speed = TimeUtils.compute_p50_output_rate(output_rates) if output_rates else 0

        self.query_one("#live-tokens", Static).update(
            f"Tokens: {tokens.total:,}"
        )
        self.query_one("#live-cost", Static).update(
            f"Cost: ${cost:.4f}"
        )
        self.query_one("#live-speed", Static).update(
            f"Speed: {p50_speed:.0f} tok/s"
        )
        self.query_one("#live-duration", Static).update(
            f"Duration: {duration}"
        )

        # Model table
        model_table = self.query_one("#live-model-table", DataTable)
        model_table.clear(columns=True)
        model_table.add_columns("Model", "Interactions", "Input", "Output", "Cost")
        model_breakdown = main.get_model_breakdown(app.pricing_data)
        for model, data in model_breakdown.items():
            tokens = data.get("tokens")
            model_table.add_row(
                model[:30],
                str(data.get("files", 0)),
                f"{tokens.input:,}" if tokens else "0",
                f"{tokens.output:,}" if tokens else "0",
                f"${data.get('cost', Decimal(0)):.4f}",
            )

        # Sub-agents table
        subagent_table = self.query_one("#live-subagent-table", DataTable)
        subagent_table.clear(columns=True)
        subagent_table.add_columns("Agent", "Model", "Tokens", "Cost", "Status")
        if wf.sub_agent_sessions:
            for sub in wf.sub_agent_sessions:
                sub_cost = sub.calculate_total_cost(app.pricing_data)
                sub_tokens = sub.total_tokens
                agent_name = sub.agent or sub.session_id[:12]
                model = ", ".join(sub.models_used[:1]) if sub.models_used else "-"
                subagent_table.add_row(
                    agent_name,
                    model,
                    f"{sub_tokens.total:,}",
                    f"${sub_cost:.4f}",
                    "active" if sub.duration_ms and sub.duration_ms > 0 else "done",
                )
        else:
            subagent_table.add_row("(no sub-agents)", "-", "-", "-", "-")

        # Tool usage table
        tool_table = self.query_one("#live-tool-table", DataTable)
        tool_table.clear(columns=True)
        tool_table.add_columns("Tool", "Calls")
        session_ids = [s.session_id for s in wf.all_sessions]
        tools = app.data_loader.load_tool_usage(session_ids)
        if tools:
            for t in tools[:15]:
                tool_table.add_row(t.tool_name, str(t.total_calls))
        else:
            tool_table.add_row("(no tool usage data)", "-")

        # Status bar
        status = self.query_one("#live-status", Label)
        status.update(
            f"Source: {self._hierarchy.get('source', '?')} | "
            f"Workflows: {len(self._workflows)} | "
            f"Sessions: {len(self._hierarchy.get('all_sessions', []))}"
        )

    def get_export_data(self):
        if self._workflow:
            return ("sessions", {"sessions": self._workflow.all_sessions})
        return None

    def action_pick_workflow(self) -> None:
        if self._workflows:
            self.app.push_screen(
                WorkflowPickerModal(self._workflows),
                callback=self._on_workflow_picked,
            )

    def _on_workflow_picked(self, workflow_id: Optional[str]) -> None:
        if workflow_id:
            for wf in self._workflows:
                if wf.workflow_id == workflow_id:
                    self._workflow = wf
                    self._update_view()
                    break

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        self.app.notify("Paused" if self._paused else "Resumed")
        if not self._paused:
            self._refresh_data()

    def action_toggle_fullscreen(self) -> None:
        try:
            sidebar = self.app.query_one("#sidebar")
            sidebar.display = not sidebar.display
        except Exception:
            pass

    def action_increase_interval(self) -> None:
        self._interval = min(60, self._interval + 1)
        self._restart_timer()
        self.app.notify(f"Refresh interval: {self._interval}s")

    def action_decrease_interval(self) -> None:
        self._interval = max(1, self._interval - 1)
        self._restart_timer()
        self.app.notify(f"Refresh interval: {self._interval}s")

    def _restart_timer(self) -> None:
        if self._timer:
            self._timer.stop()
        self._timer = self.set_interval(self._interval, self._refresh_data)


class WorkflowPickerModal(ModalScreen[Optional[str]]):
    """Modal for selecting a workflow to monitor."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, workflows: List[SessionWorkflow], **kwargs) -> None:
        super().__init__(**kwargs)
        self._workflows = workflows

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-dialog"):
            yield Label("Select Workflow")
            yield OptionList(id="workflow-list")
            with Horizontal(id="export-buttons"):
                yield Button("Cancel", variant="default", id="picker-cancel")

    def on_mount(self) -> None:
        option_list = self.query_one("#workflow-list", OptionList)
        for wf in self._workflows:
            started = (
                wf.start_time.strftime("%Y-%m-%d %H:%M") if wf.start_time else "?"
            )
            sub_info = f" (+{wf.sub_agent_count} agents)" if wf.has_sub_agents else ""
            option_list.add_option(
                f"{started} | {wf.display_title[:40]}{sub_info}"
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = event.option_index
        if 0 <= idx < len(self._workflows):
            self.dismiss(self._workflows[idx].workflow_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "picker-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
