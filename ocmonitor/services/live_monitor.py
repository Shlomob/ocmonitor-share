"""Live monitoring service for OpenCode Monitor."""

import os
import select
import sys
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, cast

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from ..config import ModelPricing, PathsConfig
from ..models.session import InteractionFile, SessionData, TokenUsage
from ..models.tool_usage import ModelToolUsage, ToolUsageStats
from ..models.workflow import SessionWorkflow
from ..ui.dashboard import DashboardUI
from ..ui.tables import TableFormatter
from ..utils.data_loader import DataLoader
from ..utils.file_utils import FileProcessor
from ..utils.sqlite_utils import SQLiteProcessor
from ..utils.time_utils import compute_p50_output_rate
from .session_grouper import SessionGrouper


class NoWorkflowsError(Exception):
    """Raised when no workflows are available for selection."""


class WorkflowWrapper:
    """Wrapper for SQLite workflow data that mimics SessionWorkflow interface."""

    def __init__(
        self, workflow_dict: Dict[str, Any], pricing_data: Dict[str, ModelPricing]
    ):
        """Initialize workflow wrapper from SQLite workflow dictionary data."""
        self.main_session: SessionData = workflow_dict["main_session"]
        self.sub_agents: List[SessionData] = workflow_dict["sub_agents"]
        self.all_sessions: List[SessionData] = workflow_dict["all_sessions"]
        self.project_name: str = workflow_dict["project_name"]
        self.display_title: str = workflow_dict["display_title"]
        self.session_count: int = workflow_dict["session_count"]
        self.sub_agent_count: int = workflow_dict["sub_agent_count"]
        self.has_sub_agents: bool = workflow_dict["has_sub_agents"]
        self.workflow_id: str = workflow_dict["workflow_id"]
        self._pricing_data = pricing_data

        # Calculate total tokens across all sessions
        self.total_tokens = TokenUsage()
        for session in self.all_sessions:
            tokens = session.total_tokens
            self.total_tokens.input += tokens.input
            self.total_tokens.output += tokens.output
            self.total_tokens.cache_write += tokens.cache_write
            self.total_tokens.cache_read += tokens.cache_read

        # Calculate time properties across all sessions
        start_times = []
        end_times = []
        for session in self.all_sessions:
            if session.start_time:
                start_times.append(session.start_time)
            if session.end_time:
                end_times.append(session.end_time)

        self.start_time: Optional[datetime] = min(start_times) if start_times else None
        self.end_time: Optional[datetime] = max(end_times) if end_times else None

        # Calculate duration
        if self.start_time and self.end_time:
            self.duration_ms: Optional[int] = int(
                (self.end_time - self.start_time).total_seconds() * 1000
            )
            self.duration_hours: float = self.duration_ms / (1000 * 60 * 60)
            self.duration_percentage: float = min(
                100.0, (self.duration_hours / 5.0) * 100
            )
        else:
            self.duration_ms = None
            self.duration_hours = 0.0
            self.duration_percentage = 0.0

    def calculate_total_cost(
        self, pricing_data: Optional[Dict[str, ModelPricing]] = None
    ) -> Decimal:
        """Calculate total cost across all sessions in workflow."""
        pricing = pricing_data or self._pricing_data
        total = Decimal("0.0")
        for session in self.all_sessions:
            total += session.calculate_total_cost(pricing)
        return total


class LiveMonitor:
    """Service for live monitoring of OpenCode sessions."""

    def __init__(
        self,
        pricing_data: Dict[str, ModelPricing],
        console: Optional[Console] = None,
        paths_config: Optional[PathsConfig] = None,
        currency_converter=None,
        init_from_db: bool = True,
    ):
        """Initialize live monitor.

        Args:
            pricing_data: Model pricing information
            console: Rich console for output
            paths_config: Path configuration for resolving default storage paths
            init_from_db: Whether to initialize active workflows from database
        """
        self.pricing_data = pricing_data
        self.console = console or Console()
        self.paths_config = paths_config
        self.currency_converter = currency_converter
        self.dashboard_ui = DashboardUI(console, currency_converter)
        self.session_grouper = SessionGrouper()
        self.data_loader = DataLoader()
        self._active_workflows: Dict[str, Any] = {}
        self._displayed_workflow_id: Optional[str] = None
        self.prev_tracked: set = set()
        self._stdin_fd: Optional[int] = None
        self._stdin_termios_state: Optional[Any] = None
        self._input_buffer: str = ""
        self._live_status_line: Optional[str] = None
        if init_from_db:
            self._initialize_active_workflows()

    def _initialize_active_workflows(self):
        """Initialize tracking of active workflows from database."""
        db_path = SQLiteProcessor.find_database_path()
        if db_path:
            workflows = SQLiteProcessor.get_all_active_workflows(db_path)
            for wf in workflows:
                wf_id = wf["workflow_id"]
                self._active_workflows[wf_id] = wf
            if self._active_workflows:
                most_recent = self._select_most_recent_workflow(
                    list(self._active_workflows.values())
                )
                self._displayed_workflow_id = most_recent["workflow_id"]
                self.prev_tracked = set(
                    s.session_id for s in most_recent["all_sessions"]
                )

    def _get_tracked_workflow_ids(self) -> Set[str]:
        """Return set of tracked workflow IDs (for testing)."""
        return set(self._active_workflows.keys())

    def _get_displayed_workflow(self) -> Optional[Dict[str, Any]]:
        """Return the currently displayed workflow (for testing)."""
        if self._displayed_workflow_id:
            return self._active_workflows.get(self._displayed_workflow_id)
        return None

    def _refresh_active_workflows(self, db_path: str):
        """Refresh active workflows from database (for testing)."""
        workflows = SQLiteProcessor.get_all_active_workflows(Path(db_path))
        current_ids = set(self._active_workflows.keys())
        new_ids = {wf["workflow_id"] for wf in workflows}
        ended_ids = current_ids - new_ids
        for ended_id in ended_ids:
            if ended_id in self._active_workflows:
                del self._active_workflows[ended_id]
        for wf in workflows:
            self._active_workflows[wf["workflow_id"]] = wf
        if self._active_workflows:
            most_recent = self._select_most_recent_workflow(
                list(self._active_workflows.values())
            )
            if self._displayed_workflow_id != most_recent["workflow_id"]:
                self._displayed_workflow_id = most_recent["workflow_id"]
                self.prev_tracked = set()
            else:
                self.prev_tracked = set(
                    s.session_id for s in most_recent["all_sessions"]
                )
        else:
            self._displayed_workflow_id = None
        self.data_loader = DataLoader()

    def _lookup_pricing_for_file(
        self, interaction_file: InteractionFile
    ) -> Optional[ModelPricing]:
        """Lookup pricing for an interaction using provider-aware fallback chain."""
        pricing = FileProcessor.lookup_pricing(
            self.pricing_data,
            model_id=interaction_file.model_id,
            provider_id=interaction_file.provider_id,
        )
        return cast(Optional[ModelPricing], pricing)

    def _get_file_active_workflows(
        self, base_path: str, allow_fallback: bool = True
    ) -> List[SessionWorkflow]:
        """Load active file-based workflows, optionally falling back to most recent."""
        sessions = FileProcessor.load_all_sessions(base_path, limit=50)
        if not sessions:
            return []

        workflows = self.session_grouper.group_sessions(sessions)
        if not workflows:
            return []

        active_workflows = [w for w in workflows if w.end_time is None]
        if active_workflows:
            return active_workflows
        return workflows[:1] if allow_fallback else []

    def _get_sqlite_active_workflows(
        self, allow_fallback: bool = True
    ) -> List[Dict[str, Any]]:
        """Load active SQLite workflows, optionally falling back to most recent."""
        db_path = SQLiteProcessor.find_database_path()
        if not db_path:
            return []

        active_workflows = SQLiteProcessor.get_all_active_workflows(db_path)
        if active_workflows:
            return active_workflows

        if not allow_fallback:
            return []

        workflow = SQLiteProcessor.get_most_recent_workflow(db_path)
        return [workflow] if workflow else []

    def _get_latest_sqlite_activity_ts(self, workflow: Dict[str, Any]) -> float:
        """Get latest parent-session activity timestamp for SQLite workflow."""
        latest = 0.0
        main_session = workflow.get("main_session")
        if main_session:
            for f in main_session.files:
                if f.time_data and f.time_data.created:
                    latest = max(latest, f.time_data.created / 1000.0)
        if (
            latest == 0.0
            and main_session
            and isinstance(main_session.start_time, datetime)
        ):
            latest = main_session.start_time.timestamp()
        return latest

    def _get_latest_file_activity_ts(self, workflow: SessionWorkflow) -> float:
        """Get latest parent-session activity timestamp for file workflow."""
        latest = 0.0
        main = workflow.main_session
        if main:
            for f in main.files:
                if f.modification_time:
                    latest = max(latest, f.modification_time.timestamp())
        return latest

    def _workflow_matches_selected_sqlite(
        self, workflow: Dict[str, Any], selected_session_id: str
    ) -> bool:
        """Check whether a SQLite workflow matches selected main/sub-agent ID."""
        if workflow.get("workflow_id") == selected_session_id:
            return True
        main_session = workflow.get("main_session")
        if main_session and main_session.session_id == selected_session_id:
            return True
        return any(
            session.session_id == selected_session_id
            for session in workflow.get("all_sessions", [])
        )

    def _workflow_matches_selected_file(
        self, workflow: SessionWorkflow, selected_session_id: str
    ) -> bool:
        """Check whether a file workflow matches selected main/sub-agent ID."""
        if workflow.workflow_id == selected_session_id:
            return True
        if workflow.main_session.session_id == selected_session_id:
            return True
        return any(
            session.session_id == selected_session_id
            for session in workflow.all_sessions
        )

    def _resolve_selected_sqlite_workflow(
        self, workflows: List[Dict[str, Any]], selected_session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Resolve selected ID to an available SQLite workflow."""
        for workflow in workflows:
            if self._workflow_matches_selected_sqlite(workflow, selected_session_id):
                return workflow
        return None

    def _resolve_selected_file_workflow(
        self, workflows: List[SessionWorkflow], selected_session_id: str
    ) -> Optional[SessionWorkflow]:
        """Resolve selected ID to an available file workflow."""
        for workflow in workflows:
            if self._workflow_matches_selected_file(workflow, selected_session_id):
                return workflow
        return None

    def _format_relative_time(self, timestamp: float) -> str:
        """Format timestamp as compact relative time."""
        if timestamp <= 0:
            return "unknown"
        elapsed = max(0, int(time.time() - timestamp))
        if elapsed < 60:
            return f"{elapsed}s ago"
        if elapsed < 3600:
            return f"{elapsed // 60}m ago"
        if elapsed < 86400:
            return f"{elapsed // 3600}h ago"
        return f"{elapsed // 86400}d ago"

    def _describe_sqlite_workflows(
        self, workflows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build human-readable descriptors for SQLite workflow selection."""
        descriptors = []
        for workflow in workflows:
            descriptors.append(
                {
                    "workflow_id": workflow["workflow_id"],
                    "display_title": workflow.get("display_title")
                    or workflow["main_session"].display_title,
                    "project_name": workflow.get("project_name")
                    or workflow["main_session"].project_name,
                    "session_count": workflow.get("session_count", 1),
                    "sub_agent_count": workflow.get("sub_agent_count", 0),
                    "last_activity_ts": self._get_latest_sqlite_activity_ts(workflow),
                }
            )
        descriptors.sort(key=lambda d: d["last_activity_ts"], reverse=True)
        return descriptors

    def _describe_file_workflows(
        self, workflows: List[SessionWorkflow]
    ) -> List[Dict[str, Any]]:
        """Build human-readable descriptors for file workflow selection."""
        descriptors = []
        for workflow in workflows:
            descriptors.append(
                {
                    "workflow_id": workflow.workflow_id,
                    "display_title": workflow.display_title,
                    "project_name": workflow.project_name,
                    "session_count": workflow.session_count,
                    "sub_agent_count": workflow.sub_agent_count,
                    "last_activity_ts": self._get_latest_file_activity_ts(workflow),
                }
            )
        descriptors.sort(key=lambda d: d["last_activity_ts"], reverse=True)
        return descriptors

    def _print_workflow_picker_table(
        self, descriptors: List[Dict[str, Any]], title: str
    ) -> None:
        """Render selection table for workflows."""
        table = Table(title=title, show_header=True)
        table.add_column("#", justify="right", style="metric.value")
        table.add_column("Session", style="table.row.main")
        table.add_column("Project", style="dashboard.project")
        table.add_column("Workflow", style="dashboard.info")
        table.add_column("Last Activity", style="table.row.time")
        table.add_column("ID", style="dim")

        for idx, descriptor in enumerate(descriptors, start=1):
            workflow_size = (
                f"{descriptor['session_count']} sessions "
                f"(1 main + {descriptor['sub_agent_count']} sub)"
            )
            table.add_row(
                str(idx),
                str(descriptor["display_title"]),
                str(descriptor["project_name"]),
                workflow_size,
                self._format_relative_time(descriptor["last_activity_ts"]),
                str(descriptor["workflow_id"]),
            )
        self.console.print(table)

    def _prompt_for_workflow_selection(
        self, descriptors: List[Dict[str, Any]], title: str
    ) -> Optional[str]:
        """Prompt user to choose workflow number from descriptors."""
        if not descriptors:
            self.console.print(
                "[status.error]No workflows available for selection.[/status.error]"
            )
            return None

        while True:
            self._print_workflow_picker_table(descriptors, title)
            choice = self.console.input(
                "[metric.label]Select workflow number (blank to cancel): [/metric.label]"
            ).strip()

            if not choice:
                return None
            if not choice.isdigit():
                self.console.print(
                    "[status.warning]Please enter a valid number.[/status.warning]"
                )
                continue

            selected_idx = int(choice)
            if selected_idx < 1 or selected_idx > len(descriptors):
                self.console.print(
                    "[status.warning]Selection out of range.[/status.warning]"
                )
                continue
            return str(descriptors[selected_idx - 1]["workflow_id"])

    def pick_sqlite_workflow(self) -> Optional[str]:
        """Interactive SQLite workflow picker."""
        workflows = self._get_sqlite_active_workflows()
        descriptors = self._describe_sqlite_workflows(workflows)
        return self._prompt_for_workflow_selection(
            descriptors, "Select Workflow (SQLite Live Monitor)"
        )

    def pick_file_workflow(self, base_path: str) -> Optional[str]:
        """Interactive file workflow picker."""
        workflows = self._get_file_active_workflows(base_path)
        descriptors = self._describe_file_workflows(workflows)
        return self._prompt_for_workflow_selection(
            descriptors, "Select Workflow (File Live Monitor)"
        )

    def _controls_hint(self, interactive_switch: bool) -> Optional[str]:
        """Return optional controls hint shown in dashboard header."""
        if not interactive_switch:
            return None
        base_hint = (
            "Workflow switching keys: n=next, p=prev, l=list, 1..9=jump, q=quit."
        )
        if self._live_status_line:
            return f"{base_hint}  Status: {self._live_status_line}"
        return base_hint

    def _handle_live_switch_command(
        self,
        command: str,
        descriptors: List[Dict[str, Any]],
        current_workflow_id: str,
    ) -> Tuple[Optional[str], bool]:
        """Process one interactive switch command.

        Returns:
            Tuple of (new_workflow_id_or_none, should_quit)
        """
        if command in {"q", "quit", "exit"}:
            self._live_status_line = "Quitting live monitor."
            return None, True

        if not descriptors:
            return None, False

        workflow_ids = [str(d["workflow_id"]) for d in descriptors]
        if current_workflow_id in workflow_ids:
            current_idx = workflow_ids.index(current_workflow_id)
        else:
            current_idx = 0

        if command in {"l", "list", "s", "show"}:
            self._print_workflow_picker_table(descriptors, "Live Workflow Switcher")
            return None, False
        if command in {"n", "next"}:
            if len(workflow_ids) == 1:
                self.console.print(
                    "[status.info]Only one active workflow available.[/status.info]"
                )
                self._live_status_line = "Only one active workflow available."
                return None, False
            self._live_status_line = "Switching to next workflow."
            return workflow_ids[(current_idx + 1) % len(workflow_ids)], False
        if command in {"p", "prev", "previous"}:
            if len(workflow_ids) == 1:
                self.console.print(
                    "[status.info]Only one active workflow available.[/status.info]"
                )
                self._live_status_line = "Only one active workflow available."
                return None, False
            self._live_status_line = "Switching to previous workflow."
            return workflow_ids[(current_idx - 1) % len(workflow_ids)], False
        if command.isdigit():
            idx = int(command) - 1
            if 0 <= idx < len(workflow_ids):
                self._live_status_line = f"Jumping to workflow #{idx + 1}."
                return workflow_ids[idx], False
            self.console.print(
                "[status.warning]Selection out of range.[/status.warning]"
            )
            self._live_status_line = "Selection out of range."
            return None, False

        self.console.print(
            "[status.warning]Unknown command. Use next/prev/list/<number>/quit (or n/p/l/q).[/status.warning]"
        )
        self._live_status_line = "Unknown command."
        return None, False

    def _apply_switch_command_selection(
        self,
        selected_session_id: Optional[str],
        current_workflow_id: str,
        new_id: Optional[str],
    ) -> Tuple[Optional[str], bool]:
        """Apply switch command result to selected target.

        Returns:
            Tuple of (updated_selected_session_id, switched)
        """
        if not new_id or new_id == current_workflow_id:
            return selected_session_id, False
        return new_id, True

    def _poll_live_switch_command(self) -> Optional[str]:
        """Poll stdin for a switch command without blocking."""
        if not sys.stdin.isatty():
            return None
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0)
        except (OSError, ValueError):
            return None
        if not ready:
            return None

        # Raw single-key mode: consume one char without echo/newline.
        if self._stdin_fd is not None:
            try:
                raw = os.read(self._stdin_fd, 1)
            except OSError:
                return None
            if not raw:
                return None

            ch = raw.decode(errors="ignore").lower()
            if ch == "\x03":  # Ctrl+C
                raise KeyboardInterrupt
            if ch in {"\r", "\n"}:
                if self._input_buffer:
                    command = self._input_buffer
                    self._input_buffer = ""
                    return command
                return None
            if ch in {"\x7f", "\b"}:  # Backspace
                self._input_buffer = self._input_buffer[:-1]
                return None

            # Fast path for ergonomic keybinds.
            if ch in {"n", "p", "l", "q"} or ch.isdigit():
                self._input_buffer = ""
                if ch == "l":
                    return "list"
                if ch == "q":
                    return "quit"
                return ch

            # Optional support for full-word commands when typed quickly.
            if ch.isalpha():
                self._input_buffer += ch
                if self._input_buffer in {
                    "next",
                    "prev",
                    "previous",
                    "list",
                    "show",
                    "quit",
                    "exit",
                }:
                    command = self._input_buffer
                    self._input_buffer = ""
                    return command
            return None

        # Fallback: canonical line mode (requires Enter).
        line = sys.stdin.readline()
        if not line:
            return None
        command = line.strip().lower()
        return command or None

    def _enable_raw_input_mode(self) -> bool:
        """Enable non-canonical no-echo input mode for live keybinds."""
        if not sys.stdin.isatty():
            return False
        try:
            import termios
        except ImportError:
            return False

        try:
            fd = sys.stdin.fileno()
            state = termios.tcgetattr(fd)
            new_state = termios.tcgetattr(fd)
            new_state[3] = new_state[3] & ~(termios.ECHO | termios.ICANON)
            termios.tcsetattr(fd, termios.TCSANOW, new_state)
            self._stdin_fd = fd
            self._stdin_termios_state = state
            self._input_buffer = ""
            return True
        except (OSError, termios.error, ValueError) as exc:
            print(
                f"Warning: failed to enable raw input mode in _enable_raw_input_mode: {exc}",
                file=sys.stderr,
            )
            self._stdin_fd = None
            self._stdin_termios_state = None
            self._input_buffer = ""
            return False

    def _disable_raw_input_mode(self) -> None:
        """Restore terminal input mode after live keybinds."""
        if self._stdin_fd is None or self._stdin_termios_state is None:
            return
        try:
            import termios

            termios.tcsetattr(
                self._stdin_fd, termios.TCSANOW, self._stdin_termios_state
            )
        except (OSError, termios.error, ValueError) as exc:
            print(
                f"Warning: failed to restore terminal mode in _disable_raw_input_mode: {exc}",
                file=sys.stderr,
            )
        finally:
            self._stdin_fd = None
            self._stdin_termios_state = None
            self._input_buffer = ""

    def _pick_workflow_during_live(
        self,
        live: Live,
        descriptors: List[Dict[str, Any]],
        title: str,
        interactive_switch: bool,
    ) -> Optional[str]:
        """Pause live view, run picker prompt, then resume live view."""
        if not descriptors:
            self.console.print(
                "[status.warning]No workflows available to pick.[/status.warning]"
            )
            return None

        raw_mode_was_enabled = self._stdin_fd is not None
        if raw_mode_was_enabled:
            self._disable_raw_input_mode()

        selected_id: Optional[str] = None
        try:
            live.stop()
            selected_id = self._prompt_for_workflow_selection(descriptors, title)
        finally:
            live.start(refresh=True)
            if interactive_switch and raw_mode_was_enabled:
                self._enable_raw_input_mode()
        return selected_id

    def _execute_workflow_switch(
        self,
        new_id: Optional[str],
        selected_session_id: Optional[str],
        current_workflow_id: str,
        current_workflow: SessionWorkflow,
        active_workflows: List[SessionWorkflow],
        live: Live,
        descriptors: List[Dict[str, Any]],
        interactive_switch: bool,
        refresh_interval: int,
    ) -> Tuple[str, SessionWorkflow, Optional[str]]:
        """Execute workflow switch with state updates.

        Args:
            new_id: Target workflow ID to switch to
            selected_session_id: Currently selected session ID (if any)
            current_workflow_id: Current workflow ID
            current_workflow: Current workflow object
            active_workflows: List of available workflows
            live: Rich Live instance for updates
            descriptors: Workflow descriptors for display
            interactive_switch: Whether keyboard controls enabled
            refresh_interval: Update frequency in seconds

        Returns:
            Tuple of (updated_workflow_id, updated_workflow, updated_selected_session_id)
        """
        selected_session_id, switched = self._apply_switch_command_selection(
            selected_session_id, current_workflow_id, new_id
        )

        if not switched or not selected_session_id:
            return current_workflow_id, current_workflow, selected_session_id

        self.prev_tracked = set()
        self._live_status_line = f"Switched to workflow {selected_session_id}."
        self.console.print(
            f"[status.info]Switched to workflow [metric.value]{selected_session_id}[/metric.value][/status.info]"
        )

        immediate_current = self._resolve_selected_file_workflow(
            active_workflows, selected_session_id
        )

        if not immediate_current:
            return current_workflow_id, current_workflow, selected_session_id

        if immediate_current.workflow_id != current_workflow_id:
            current_workflow_id = immediate_current.workflow_id
            self.prev_tracked = set()

        current_workflow = immediate_current
        self.prev_tracked |= set(s.session_id for s in current_workflow.all_sessions)

        live.update(
            self._generate_workflow_dashboard(
                current_workflow, self._controls_hint(interactive_switch)
            )
        )

        return current_workflow_id, current_workflow, selected_session_id

    def _handle_list_command(
        self,
        live: Live,
        descriptors: List[Dict[str, Any]],
        selected_session_id: Optional[str],
        current_workflow_id: str,
        current_workflow: SessionWorkflow,
        active_workflows: List[SessionWorkflow],
        interactive_switch: bool,
        refresh_interval: int,
    ) -> Tuple[str, SessionWorkflow, Optional[str]]:
        """Handle list/picker workflow switch command.

        Args:
            live: Rich Live instance
            descriptors: Workflow descriptors for display
            selected_session_id: Currently selected session ID
            current_workflow_id: Current workflow ID
            current_workflow: Current workflow object
            active_workflows: List of available workflows
            interactive_switch: Whether keyboard controls enabled
            refresh_interval: Update frequency in seconds

        Returns:
            Tuple of (updated_workflow_id, updated_workflow, updated_selected_session_id)
        """
        selected_from_picker = self._pick_workflow_during_live(
            live, descriptors, "Live Workflow Switcher", interactive_switch
        )
        if not selected_from_picker:
            return current_workflow_id, current_workflow, selected_session_id

        return self._execute_workflow_switch(
            selected_from_picker,
            selected_session_id,
            current_workflow_id,
            current_workflow,
            active_workflows,
            live,
            descriptors,
            interactive_switch,
            refresh_interval,
        )

    def _handle_navigation_command(
        self,
        command: str,
        descriptors: List[Dict[str, Any]],
        selected_session_id: Optional[str],
        current_workflow_id: str,
        current_workflow: SessionWorkflow,
        active_workflows: List[SessionWorkflow],
        live: Live,
        interactive_switch: bool,
        refresh_interval: int,
    ) -> Tuple[bool, str, SessionWorkflow, Optional[str]]:
        """Handle n/p/1-9 navigation commands.

        Args:
            command: The command string (n, p, 1-9, etc)
            descriptors: Workflow descriptors
            selected_session_id: Currently selected session ID
            current_workflow_id: Current workflow ID
            current_workflow: Current workflow object
            active_workflows: List of available workflows
            live: Rich Live instance
            interactive_switch: Whether keyboard controls enabled
            refresh_interval: Update frequency in seconds

        Returns:
            Tuple of (should_quit, updated_workflow_id, updated_workflow, updated_selected_session_id)
        """
        new_id, should_quit = self._handle_live_switch_command(
            command, descriptors, current_workflow_id
        )
        if should_quit:
            return True, current_workflow_id, current_workflow, selected_session_id

        new_workflow_id, new_workflow, new_selected = self._execute_workflow_switch(
            new_id,
            selected_session_id,
            current_workflow_id,
            current_workflow,
            active_workflows,
            live,
            descriptors,
            interactive_switch,
            refresh_interval,
        )
        return False, new_workflow_id, new_workflow, new_selected

    def start_monitoring(
        self,
        base_path: str,
        refresh_interval: int = 5,
        selected_session_id: Optional[str] = None,
        interactive_switch: bool = False,
        inline: bool = False,
    ):
        """Start live monitoring of all active workflows (main session + sub-agents).

        Tracks all active (ongoing) workflows and displays the one with most recent activity.

        Args:
            base_path: Path to directory containing sessions
            refresh_interval: Update interval in seconds
            selected_session_id: Optional workflow/main/sub-agent ID to pin
            interactive_switch: Enable command-driven live workflow switching
            inline: Keep dashboard output in the normal terminal buffer
        """
        try:
            active_workflows = self._get_file_active_workflows(
                base_path, allow_fallback=not bool(selected_session_id)
            )
            if not active_workflows:
                self.console.print(
                    f"[status.error]No sessions found in {base_path}[/status.error]"
                )
                return

            if selected_session_id:
                current_workflow = self._resolve_selected_file_workflow(
                    active_workflows, selected_session_id
                )
                if not current_workflow:
                    self.console.print(
                        f"[status.error]Selected session/workflow '{selected_session_id}' is not available.[/status.error]"
                    )
                    return
            else:
                current_workflow = self._select_most_recent_file_workflow(
                    active_workflows
                )

            current_workflow_id = current_workflow.workflow_id
            self.prev_tracked = set(s.session_id for s in current_workflow.all_sessions)

            self.console.print(
                f"[status.success]Starting live monitoring of workflow: {current_workflow.main_session.session_id}[/status.success]"
            )
            if selected_session_id:
                self.console.print(
                    f"[status.info]Pinned mode: tracking selected ID [metric.value]{selected_session_id}[/metric.value][/status.info]"
                )
            else:
                self.console.print(
                    "[status.info]Auto mode: showing most recently active workflow[/status.info]"
                )
            if current_workflow.has_sub_agents:
                self.console.print(
                    f"[status.info]Tracking {current_workflow.session_count} sessions (1 main + {current_workflow.sub_agent_count} sub-agents)[/status.info]"
                )
            if len(active_workflows) > 1:
                self.console.print(
                    f"[status.info]Monitoring {len(active_workflows)} active workflows[/status.info]"
                )
            self.console.print(
                f"[status.info]Update interval: {refresh_interval} seconds[/status.info]"
            )
            if interactive_switch:
                raw_mode_enabled = self._enable_raw_input_mode()
                self._live_status_line = "Ready."
                self.console.print(
                    "[status.info]Interactive switching enabled: press n/p/l/1..9/q[/status.info]"
                )
                if not raw_mode_enabled:
                    self.console.print(
                        "[status.warning]Raw key mode unavailable; fallback requires Enter.[/status.warning]"
                    )
                    self._live_status_line = (
                        "Raw-key mode unavailable; commands require Enter."
                    )
            self.console.print("[dim]Press Ctrl+C to exit[/dim]\n")

            with Live(
                self._generate_workflow_dashboard(
                    current_workflow, self._controls_hint(interactive_switch)
                ),
                refresh_per_second=10,
                console=self.console,
                screen=not inline,
            ) as live:
                descriptors = self._describe_file_workflows(active_workflows)
                next_refresh_at = time.time() + refresh_interval
                while True:
                    if interactive_switch:
                        command = self._poll_live_switch_command()
                        if command:
                            prev_workflow_id = current_workflow_id
                            if command in {"l", "list", "s", "show"}:
                                (
                                    current_workflow_id,
                                    current_workflow,
                                    selected_session_id,
                                ) = self._handle_list_command(
                                    live,
                                    descriptors,
                                    selected_session_id,
                                    current_workflow_id,
                                    current_workflow,
                                    active_workflows,
                                    interactive_switch,
                                    refresh_interval,
                                )
                                if current_workflow_id != prev_workflow_id:
                                    next_refresh_at = time.time() + refresh_interval
                                continue

                            (
                                should_quit,
                                current_workflow_id,
                                current_workflow,
                                selected_session_id,
                            ) = self._handle_navigation_command(
                                command,
                                descriptors,
                                selected_session_id,
                                current_workflow_id,
                                current_workflow,
                                active_workflows,
                                live,
                                interactive_switch,
                                refresh_interval,
                            )
                            if current_workflow_id != prev_workflow_id:
                                next_refresh_at = time.time() + refresh_interval
                            if should_quit:
                                self.console.print(
                                    "\n[status.warning]Live monitoring stopped.[/status.warning]"
                                )
                                break

                    if time.time() < next_refresh_at:
                        time.sleep(0.05)
                        continue

                    active_workflows = self._get_file_active_workflows(
                        base_path, allow_fallback=not bool(selected_session_id)
                    )
                    descriptors = self._describe_file_workflows(active_workflows)

                    if not active_workflows:
                        self.console.print(
                            "[status.warning]No workflows available to monitor.[/status.warning]"
                        )
                        break

                    if selected_session_id:
                        new_current = self._resolve_selected_file_workflow(
                            active_workflows, selected_session_id
                        )
                        if not new_current:
                            self.console.print(
                                f"[status.warning]Selected session/workflow '{selected_session_id}' is no longer active. Stopping monitor.[/status.warning]"
                            )
                            break
                    else:
                        new_current = self._select_most_recent_file_workflow(
                            active_workflows
                        )

                    if new_current.workflow_id != current_workflow_id:
                        current_workflow_id = new_current.workflow_id
                        self.prev_tracked = set()
                    current_workflow = new_current

                    self.prev_tracked |= set(
                        s.session_id for s in current_workflow.all_sessions
                    )

                    live.update(
                        self._generate_workflow_dashboard(
                            current_workflow, self._controls_hint(interactive_switch)
                        )
                    )
                    next_refresh_at = time.time() + refresh_interval

        except KeyboardInterrupt:
            self.console.print(
                "\n[status.warning]Live monitoring stopped.[/status.warning]"
            )
        finally:
            self._disable_raw_input_mode()

    def _generate_dashboard(self, session: SessionData):
        """Generate dashboard layout for the session.

        Args:
            session: Session to monitor

        Returns:
            Rich layout for the dashboard
        """
        # Get the most recent file (excluding zero-token files)
        recent_file = None
        if session.non_zero_token_files:
            recent_file = max(
                session.non_zero_token_files, key=lambda f: f.modification_time
            )
        elif session.files:
            recent_file = max(session.files, key=lambda f: f.modification_time)

        # Get model pricing for quota
        quota = None
        if recent_file:
            pricing = self._lookup_pricing_for_file(recent_file)
            if pricing is not None:
                quota = pricing.session_quota

        # Calculate per-model output rates for this session
        per_model_output_rates = self._calculate_session_output_rates(session)
        per_model_context = self._get_session_context_usage(session)

        return self.dashboard_ui.create_dashboard_layout(
            session=session,
            recent_file=recent_file,
            pricing_data=self.pricing_data,
            quota=quota,
            per_model_output_rates=per_model_output_rates,
            per_model_context=per_model_context,
        )

    def _calculate_session_output_rates(self, session: SessionData) -> Dict[str, float]:
        """Calculate p50 output token rate per model for a single session.

        For each model, collects eligible interactions and computes p50 rate.

        Args:
            session: Session to analyze

        Returns:
            Dict mapping model_id to p50 output tokens per second
        """
        if not session.files:
            return {}

        model_files: Dict[str, List[InteractionFile]] = {}
        for f in session.non_zero_token_files:
            if f.model_id not in model_files:
                model_files[f.model_id] = []
            model_files[f.model_id].append(f)

        result = {}
        for model_id, files in model_files.items():
            result[model_id] = compute_p50_output_rate(files)

        return result

    def _get_session_context_usage(
        self, session: SessionData
    ) -> Dict[str, Dict[str, Any]]:
        """Get context window usage for each model in a single session.

        For each model, finds the most recent interaction and calculates context usage.

        Args:
            session: Session to analyze

        Returns:
            Dict mapping model_id to context usage info (context_size, context_window, usage_percentage)
        """
        if not session.files:
            return {}

        model_most_recent: Dict[str, InteractionFile] = {}
        for f in session.non_zero_token_files:
            if f.model_id not in model_most_recent:
                model_most_recent[f.model_id] = f
            elif f.modification_time > model_most_recent[f.model_id].modification_time:
                model_most_recent[f.model_id] = f

        result = {}
        default_context_window = 200000

        for model_id, recent_file in model_most_recent.items():
            pricing = self._lookup_pricing_for_file(recent_file)
            if pricing is not None:
                context_window = pricing.context_window
            else:
                context_window = default_context_window

            context_size = (
                recent_file.tokens.input
                + recent_file.tokens.cache_read
                + recent_file.tokens.cache_write
            )

            usage_pct = (
                (context_size / context_window) * 100 if context_window > 0 else 0
            )

            result[model_id] = {
                "context_size": context_size,
                "context_window": context_window,
                "usage_percentage": min(100.0, usage_pct),
            }

        return result

    def _generate_workflow_dashboard(
        self, workflow: SessionWorkflow, controls_hint: Optional[str] = None
    ):
        """Generate dashboard layout for a workflow (main + sub-agents).

        Args:
            workflow: Workflow to monitor

        Returns:
            Rich layout for the dashboard
        """
        # Get all files from all sessions in the workflow
        all_files: List[InteractionFile] = []
        for session in workflow.all_sessions:
            all_files.extend(session.non_zero_token_files)

        # Get the most recent file across all sessions
        recent_file = None
        if all_files:
            recent_file = max(all_files, key=lambda f: f.modification_time)

        # Calculate per-model output rates
        per_model_output_rates = self._calculate_per_model_output_rates(workflow)

        # Calculate per-model context usage
        per_model_context = self._get_per_model_context_usage(workflow)

        # Get model pricing for quota
        quota = None
        if recent_file:
            pricing = self._lookup_pricing_for_file(recent_file)
            if pricing is not None:
                quota = pricing.session_quota

        # Load tool usage statistics (file mode - no SQLite fallback)
        tool_stats = self._load_tool_stats_for_workflow(
            workflow, preferred_source="files"
        )
        tool_stats_by_model = self._load_tool_stats_by_model_for_workflow(
            workflow, preferred_source="files"
        )

        # Create a combined session-like view for the dashboard
        # We'll pass workflow info to the dashboard UI
        return self.dashboard_ui.create_dashboard_layout(
            session=workflow.main_session,
            recent_file=recent_file,
            pricing_data=self.pricing_data,
            quota=quota,
            per_model_output_rates=per_model_output_rates,
            per_model_context=per_model_context,
            workflow=workflow,  # Pass workflow for additional display
            tool_stats=tool_stats,
            tool_stats_by_model=tool_stats_by_model,
            controls_hint=controls_hint,
        )

    def _calculate_per_model_output_rates(
        self, workflow: SessionWorkflow
    ) -> Dict[str, float]:
        """Calculate p50 output token rate per model across workflow.

        For each model, collects eligible interactions and computes p50 rate.

        Args:
            workflow: Workflow containing all sessions

        Returns:
            Dict mapping model_id to p50 output tokens per second
        """
        model_files: Dict[str, List[InteractionFile]] = {}
        for session in workflow.all_sessions:
            for f in session.non_zero_token_files:
                if f.model_id not in model_files:
                    model_files[f.model_id] = []
                model_files[f.model_id].append(f)

        if not model_files:
            return {}

        result = {}
        for model_id, files in model_files.items():
            result[model_id] = compute_p50_output_rate(files)

        return result

    def _get_per_model_context_usage(
        self, workflow: SessionWorkflow
    ) -> Dict[str, Dict[str, Any]]:
        """Get context window usage for each model in workflow.

        For each model, finds the most recent interaction and calculates context usage.

        Args:
            workflow: Workflow containing all sessions

        Returns:
            Dict mapping model_id to context usage info (context_size, context_window, usage_percentage)
        """
        all_files: List[InteractionFile] = []
        for session in workflow.all_sessions:
            all_files.extend(session.non_zero_token_files)

        if not all_files:
            return {}

        model_most_recent: Dict[str, InteractionFile] = {}
        for f in all_files:
            if f.model_id not in model_most_recent:
                model_most_recent[f.model_id] = f
            elif f.modification_time > model_most_recent[f.model_id].modification_time:
                model_most_recent[f.model_id] = f

        result = {}
        default_context_window = 200000

        for model_id, recent_file in model_most_recent.items():
            pricing = self._lookup_pricing_for_file(recent_file)
            if pricing is not None:
                context_window = pricing.context_window
            else:
                context_window = default_context_window

            context_size = (
                recent_file.tokens.input
                + recent_file.tokens.cache_read
                + recent_file.tokens.cache_write
            )

            usage_pct = (
                (context_size / context_window) * 100 if context_window > 0 else 0
            )

            result[model_id] = {
                "context_size": context_size,
                "context_window": context_window,
                "usage_percentage": min(100.0, usage_pct),
            }

        return result

    def _calculate_output_rate(self, session: SessionData) -> float:
        """Calculate p50 output token rate over the last 5 minutes of activity.

        Args:
            session: SessionData object containing all interactions

        Returns:
            P50 output tokens per second over the last 5 minutes
        """
        if not session.files:
            return 0.0

        # Calculate the cutoff time (5 minutes ago)
        cutoff_time = datetime.now() - timedelta(minutes=5)

        # Filter interactions from the last 5 minutes
        recent_interactions = [
            f for f in session.files if f.modification_time >= cutoff_time
        ]

        if not recent_interactions:
            return 0.0

        # Compute p50 from eligible interactions in the window
        rate = compute_p50_output_rate(recent_interactions)
        if rate > 0:
            return rate

        # Fallback: aggregate mean for the window if no eligible interactions
        total_output_tokens = sum(f.tokens.output for f in recent_interactions)
        if total_output_tokens == 0:
            return 0.0

        total_duration_ms = 0
        for f in recent_interactions:
            if f.time_data and f.time_data.duration_ms:
                total_duration_ms += f.time_data.duration_ms

        total_duration_seconds = total_duration_ms / 1000

        if total_duration_seconds > 0:
            return total_output_tokens / total_duration_seconds

        return 0.0

    def _load_tool_stats_for_workflow(
        self,
        workflow: Any,
        preferred_source: Optional[Literal["sqlite", "files"]] = None,
    ) -> List[ToolUsageStats]:
        """Load tool usage statistics for a workflow's sessions.

        Args:
            workflow: Workflow object (SessionWorkflow or WorkflowWrapper)
            preferred_source: Override source selection ("sqlite" or "files").
                Ensures file-mode monitoring doesn't fall back to SQLite.

        Returns:
            List of ToolUsageStats sorted by total_calls descending
        """
        session_ids = [s.session_id for s in workflow.all_sessions]
        return self.data_loader.load_tool_usage(session_ids, preferred_source)

    def _load_tool_stats_by_model_for_workflow(
        self,
        workflow: Any,
        preferred_source: Optional[Literal["sqlite", "files"]] = None,
    ) -> List[ModelToolUsage]:
        """Load tool usage statistics grouped by model for a workflow's sessions.

        Args:
            workflow: Workflow object (SessionWorkflow or WorkflowWrapper)
            preferred_source: Override source selection ("sqlite" or "files").
                Ensures file-mode monitoring doesn't fall back to SQLite.

        Returns:
            List of ModelToolUsage sorted by total_calls descending
        """
        session_ids = [s.session_id for s in workflow.all_sessions]
        return self.data_loader.load_tool_usage_by_model(session_ids, preferred_source)

    def get_session_status(self, base_path: str) -> Dict[str, Any]:
        """Get current status of the most recent session.

        Args:
            base_path: Path to directory containing sessions

        Returns:
            Dictionary with session status information
        """
        recent_session = FileProcessor.get_most_recent_session(base_path)
        if not recent_session:
            return {"status": "no_sessions", "message": "No sessions found"}

        recent_file = None
        if recent_session.files:
            recent_file = max(recent_session.files, key=lambda f: f.modification_time)

        # Calculate how long ago the last activity was
        last_activity = None
        if recent_file:
            last_activity = time.time() - recent_file.modification_time.timestamp()

        # Determine activity status
        activity_status = "unknown"
        if last_activity is not None:
            if last_activity < 60:  # Less than 1 minute
                activity_status = "active"
            elif last_activity < 300:  # Less than 5 minutes
                activity_status = "recent"
            elif last_activity < 1800:  # Less than 30 minutes
                activity_status = "idle"
            else:
                activity_status = "inactive"

        return {
            "status": "found",
            "session_id": recent_session.session_id,
            "interaction_count": recent_session.interaction_count,
            "total_tokens": recent_session.total_tokens.total,
            "total_cost": float(recent_session.calculate_total_cost(self.pricing_data)),
            "models_used": recent_session.models_used,
            "last_activity_seconds": last_activity,
            "activity_status": activity_status,
            "output_rate": self._calculate_output_rate(recent_session),
            "recent_file": {
                "name": recent_file.file_name,
                "model": recent_file.model_id,
                "tokens": recent_file.tokens.total,
            }
            if recent_file
            else None,
        }

    def monitor_single_update(self, base_path: str) -> Optional[Dict[str, Any]]:
        """Get a single update of the monitoring data.

        Args:
            base_path: Path to directory containing sessions

        Returns:
            Monitoring data or None if no session found
        """
        recent_session = FileProcessor.get_most_recent_session(base_path)
        if not recent_session:
            return None

        recent_file = None
        if recent_session.files:
            recent_file = max(recent_session.files, key=lambda f: f.modification_time)

        return {
            "timestamp": time.time(),
            "session": {
                "id": recent_session.session_id,
                "interaction_count": recent_session.interaction_count,
                "total_tokens": recent_session.total_tokens.model_dump(),
                "total_cost": float(
                    recent_session.calculate_total_cost(self.pricing_data)
                ),
                "models_used": recent_session.models_used,
            },
            "recent_interaction": {
                "file_name": recent_file.file_name,
                "model_id": recent_file.model_id,
                "tokens": recent_file.tokens.model_dump(),
                "cost": float(recent_file.calculate_cost(self.pricing_data)),
                "modification_time": recent_file.modification_time.isoformat(),
            }
            if recent_file
            else None,
            "output_rate": self._calculate_output_rate(recent_session),
            "context_usage": self._calculate_context_usage(recent_file)
            if recent_file
            else None,
        }

    def _calculate_context_usage(
        self, interaction_file: InteractionFile
    ) -> Dict[str, Any]:
        """Calculate context window usage for an interaction.

        Args:
            interaction_file: Interaction file to analyze

        Returns:
            Context usage information
        """
        model_pricing = self._lookup_pricing_for_file(interaction_file)
        if model_pricing is None:
            return {
                "context_size": 0,
                "context_window": 200000,
                "usage_percentage": 0.0,
            }

        context_window = model_pricing.context_window

        # Context size = input + cache read + cache write
        context_size = (
            interaction_file.tokens.input
            + interaction_file.tokens.cache_read
            + interaction_file.tokens.cache_write
        )

        usage_percentage = (
            (context_size / context_window) * 100 if context_window > 0 else 0
        )

        return {
            "context_size": context_size,
            "context_window": context_window,
            "usage_percentage": min(100.0, usage_percentage),
        }

    def start_sqlite_workflow_monitoring(
        self,
        refresh_interval: int = 5,
        selected_session_id: Optional[str] = None,
        interactive_switch: bool = False,
        inline: bool = False,
    ):
        """Start live monitoring of all active workflows from SQLite (v1.2.0+).

        Tracks all active (ongoing) workflows and displays the one with most recent activity.
        Shows the current workflow (main session + sub-agents) with detailed metrics.

        Args:
            refresh_interval: Update interval in seconds
            selected_session_id: Optional workflow/main/sub-agent ID to pin
            interactive_switch: Enable command-driven live workflow switching
            inline: Keep dashboard output in the normal terminal buffer
        """
        try:
            # Check if SQLite is available
            db_path = SQLiteProcessor.find_database_path()
            if not db_path:
                self.console.print(
                    "[status.error]SQLite database not found.[/status.error]"
                )
                return

            active_workflows = self._get_sqlite_active_workflows(
                allow_fallback=not bool(selected_session_id)
            )
            if not active_workflows:
                self.console.print(
                    "[status.error]No sessions found in database.[/status.error]"
                )
                return

            if selected_session_id:
                current_workflow = self._resolve_selected_sqlite_workflow(
                    active_workflows, selected_session_id
                )
                if not current_workflow:
                    self.console.print(
                        f"[status.error]Selected session/workflow '{selected_session_id}' is not available.[/status.error]"
                    )
                    return
            else:
                current_workflow = self._select_most_recent_workflow(active_workflows)

            current_workflow_id = current_workflow["workflow_id"]
            self.prev_tracked = set(
                s.session_id for s in current_workflow["all_sessions"]
            )

            self.console.print(
                f"[status.success]Starting live monitoring of workflow: {current_workflow_id}[/status.success]"
            )
            if selected_session_id:
                self.console.print(
                    f"[status.info]Pinned mode: tracking selected ID [metric.value]{selected_session_id}[/metric.value][/status.info]"
                )
            else:
                self.console.print(
                    "[status.info]Auto mode: showing most recently active workflow[/status.info]"
                )
            if current_workflow["has_sub_agents"]:
                self.console.print(
                    f"[status.info]Tracking {current_workflow['session_count']} sessions (1 main + {current_workflow['sub_agent_count']} sub-agents)[/status.info]"
                )
            if len(active_workflows) > 1:
                self.console.print(
                    f"[status.info]Monitoring {len(active_workflows)} active workflows[/status.info]"
                )
            self.console.print(
                f"[status.info]Update interval: {refresh_interval} seconds[/status.info]"
            )
            if interactive_switch:
                raw_mode_enabled = self._enable_raw_input_mode()
                self._live_status_line = "Ready."
                self.console.print(
                    "[status.info]Interactive switching enabled: press n/p/l/1..9/q[/status.info]"
                )
                if not raw_mode_enabled:
                    self.console.print(
                        "[status.warning]Raw key mode unavailable; fallback requires Enter.[/status.warning]"
                    )
                    self._live_status_line = (
                        "Raw-key mode unavailable; commands require Enter."
                    )
            self.console.print("[dim]Press Ctrl+C to exit[/dim]\n")

            # Start live monitoring
            with Live(
                self._generate_sqlite_workflow_dashboard(
                    current_workflow, self._controls_hint(interactive_switch)
                ),
                refresh_per_second=10,
                console=self.console,
                screen=not inline,
            ) as live:
                descriptors = self._describe_sqlite_workflows(active_workflows)
                next_refresh_at = time.time() + refresh_interval
                while True:
                    if interactive_switch:
                        command = self._poll_live_switch_command()
                        if command:
                            if command in {"l", "list", "s", "show"}:
                                selected_from_picker = self._pick_workflow_during_live(
                                    live,
                                    descriptors,
                                    "Live Workflow Switcher",
                                    interactive_switch,
                                )
                                if selected_from_picker:
                                    selected_session_id, switched = (
                                        self._apply_switch_command_selection(
                                            selected_session_id,
                                            current_workflow_id,
                                            selected_from_picker,
                                        )
                                    )
                                    if switched and selected_session_id:
                                        self.prev_tracked = set()
                                        self._live_status_line = f"Switched to workflow {selected_session_id}."
                                        self.console.print(
                                            f"[status.info]Switched to workflow [metric.value]{selected_session_id}[/metric.value][/status.info]"
                                        )
                                        immediate_current = (
                                            self._resolve_selected_sqlite_workflow(
                                                active_workflows, selected_session_id
                                            )
                                        )
                                        if immediate_current:
                                            if (
                                                immediate_current["workflow_id"]
                                                != current_workflow_id
                                            ):
                                                current_workflow_id = immediate_current[
                                                    "workflow_id"
                                                ]
                                                self.prev_tracked = set()
                                            current_workflow = immediate_current
                                            self.prev_tracked |= set(
                                                s.session_id
                                                for s in current_workflow[
                                                    "all_sessions"
                                                ]
                                            )
                                            live.update(
                                                self._generate_sqlite_workflow_dashboard(
                                                    current_workflow,
                                                    self._controls_hint(
                                                        interactive_switch
                                                    ),
                                                )
                                            )
                                            next_refresh_at = (
                                                time.time() + refresh_interval
                                            )
                                continue

                            new_id, should_quit = self._handle_live_switch_command(
                                command, descriptors, current_workflow_id
                            )
                            if should_quit:
                                self.console.print(
                                    "\n[status.warning]Live monitoring stopped.[/status.warning]"
                                )
                                break
                            selected_session_id, switched = (
                                self._apply_switch_command_selection(
                                    selected_session_id,
                                    current_workflow_id,
                                    new_id,
                                )
                            )
                            if switched and selected_session_id:
                                self.prev_tracked = set()
                                self._live_status_line = (
                                    f"Switched to workflow {selected_session_id}."
                                )
                                self.console.print(
                                    f"[status.info]Switched to workflow [metric.value]{selected_session_id}[/metric.value][/status.info]"
                                )
                                immediate_current = (
                                    self._resolve_selected_sqlite_workflow(
                                        active_workflows, selected_session_id
                                    )
                                )
                                if immediate_current:
                                    if (
                                        immediate_current["workflow_id"]
                                        != current_workflow_id
                                    ):
                                        current_workflow_id = immediate_current[
                                            "workflow_id"
                                        ]
                                        self.prev_tracked = set()
                                    current_workflow = immediate_current
                                    self.prev_tracked |= set(
                                        s.session_id
                                        for s in current_workflow["all_sessions"]
                                    )
                                    live.update(
                                        self._generate_sqlite_workflow_dashboard(
                                            current_workflow,
                                            self._controls_hint(interactive_switch),
                                        )
                                    )
                                    next_refresh_at = time.time() + refresh_interval

                    if time.time() < next_refresh_at:
                        time.sleep(0.05)
                        continue

                    active_workflows = self._get_sqlite_active_workflows(
                        allow_fallback=not bool(selected_session_id)
                    )
                    descriptors = self._describe_sqlite_workflows(active_workflows)

                    if not active_workflows:
                        self.console.print(
                            "[status.warning]No workflows available to monitor.[/status.warning]"
                        )
                        break

                    if selected_session_id:
                        new_current = self._resolve_selected_sqlite_workflow(
                            active_workflows, selected_session_id
                        )
                        if not new_current:
                            self.console.print(
                                f"[status.warning]Selected session/workflow '{selected_session_id}' is no longer active. Stopping monitor.[/status.warning]"
                            )
                            break
                    else:
                        new_current = self._select_most_recent_workflow(
                            active_workflows
                        )

                    if new_current["workflow_id"] != current_workflow_id:
                        current_workflow_id = new_current["workflow_id"]
                        self.prev_tracked = set()
                    current_workflow = new_current
                    self.prev_tracked |= set(
                        s.session_id for s in current_workflow["all_sessions"]
                    )

                    live.update(
                        self._generate_sqlite_workflow_dashboard(
                            current_workflow, self._controls_hint(interactive_switch)
                        )
                    )
                    next_refresh_at = time.time() + refresh_interval

        except KeyboardInterrupt:
            self.console.print(
                "\n[status.warning]Live monitoring stopped.[/status.warning]"
            )
        finally:
            self._disable_raw_input_mode()

    def _select_most_recent_workflow(
        self, workflows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Select the workflow with most recent activity.

        Args:
            workflows: List of workflow dicts

        Returns:
            The workflow with the most recent file modification
        """
        if not workflows:
            raise NoWorkflowsError()
        if len(workflows) == 1:
            return workflows[0]

        def get_latest_activity(workflow: Dict[str, Any]) -> float:
            """Return latest parent-session activity timestamp for workflow sorting."""
            latest = 0.0
            has_file_activity = False
            main_session = workflow.get("main_session")
            if main_session:
                for f in main_session.files:
                    if f.time_data and f.time_data.created:
                        latest = max(latest, f.time_data.created / 1000.0)
                        has_file_activity = True
            if not has_file_activity and main_session:
                start_time = main_session.start_time
                if isinstance(start_time, datetime):
                    latest = start_time.timestamp()
                elif isinstance(start_time, (int, float)):
                    latest = float(start_time)
                else:
                    latest = 0.0
            return latest

        return max(workflows, key=get_latest_activity)

    def _select_most_recent_file_workflow(
        self, workflows: List[SessionWorkflow]
    ) -> SessionWorkflow:
        """Select the file-based workflow with most recent activity.

        Args:
            workflows: List of SessionWorkflow objects

        Returns:
            The workflow with the most recent file modification
        """
        if not workflows:
            raise NoWorkflowsError()
        if len(workflows) == 1:
            return workflows[0]

        def get_latest_parent_activity(workflow: SessionWorkflow) -> float:
            """Return latest main-session file modification timestamp."""
            latest = 0.0
            main = workflow.main_session
            if main:
                for f in main.files:
                    if f.modification_time:
                        latest = max(latest, f.modification_time.timestamp())
            return latest

        return max(workflows, key=get_latest_parent_activity)

    def _generate_sqlite_workflow_dashboard(
        self, workflow: Dict[str, Any], controls_hint: Optional[str] = None
    ):
        """Generate dashboard layout for a SQLite workflow (main + sub-agents).

        Args:
            workflow: Workflow dict from SQLiteProcessor.get_most_recent_workflow()

        Returns:
            Rich layout for the dashboard
        """
        # Get all files from all sessions in the workflow
        all_files = []
        for session in workflow["all_sessions"]:
            all_files.extend(session.non_zero_token_files)

        # Get the most recent file across all sessions
        recent_file = None
        if all_files:
            recent_file = max(
                all_files,
                key=lambda f: (
                    f.time_data.created if f.time_data and f.time_data.created else 0
                ),
            )

        # Calculate per-model output rates for SQLite workflow
        per_model_output_rates = self._calculate_sqlite_per_model_output_rates(workflow)

        # Calculate per-model context usage for SQLite workflow
        per_model_context = self._get_sqlite_per_model_context_usage(workflow)

        # Get model pricing for quota
        quota = None
        if recent_file:
            pricing = self._lookup_pricing_for_file(recent_file)
            if pricing is not None:
                quota = pricing.session_quota

        # Create a workflow wrapper for the dashboard UI
        workflow_wrapper = WorkflowWrapper(workflow, self.pricing_data)

        # Load tool usage statistics (SQLite mode)
        tool_stats = self._load_tool_stats_for_workflow(
            workflow_wrapper, preferred_source="sqlite"
        )
        tool_stats_by_model = self._load_tool_stats_by_model_for_workflow(
            workflow_wrapper, preferred_source="sqlite"
        )

        # Use the existing dashboard UI
        # Note: WorkflowWrapper mimics SessionWorkflow interface for dashboard compatibility

        return self.dashboard_ui.create_dashboard_layout(
            session=workflow["main_session"],
            recent_file=recent_file,
            pricing_data=self.pricing_data,
            quota=quota,
            per_model_output_rates=per_model_output_rates,
            per_model_context=per_model_context,
            workflow=cast(Any, workflow_wrapper),
            tool_stats=tool_stats,
            tool_stats_by_model=tool_stats_by_model,
            controls_hint=controls_hint,
        )

    def _calculate_sqlite_per_model_output_rates(
        self, workflow: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate p50 output token rate per model for SQLite workflow.

        For each model, collects eligible interactions and computes p50 rate.

        Args:
            workflow: Workflow dict from SQLite

        Returns:
            Dict mapping model_id to p50 output tokens per second
        """
        model_files: Dict[str, List[InteractionFile]] = {}
        for session in workflow["all_sessions"]:
            for f in session.non_zero_token_files:
                if f.model_id not in model_files:
                    model_files[f.model_id] = []
                model_files[f.model_id].append(f)

        if not model_files:
            return {}

        result = {}
        for model_id, files in model_files.items():
            result[model_id] = compute_p50_output_rate(files)

        return result

    def _get_sqlite_per_model_context_usage(
        self, workflow: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Get context window usage for each model in SQLite workflow.

        For each model, finds the most recent interaction and calculates context usage.

        Args:
            workflow: Workflow dict from SQLite

        Returns:
            Dict mapping model_id to context usage info
        """
        all_files = []
        for session in workflow["all_sessions"]:
            all_files.extend(session.non_zero_token_files)

        if not all_files:
            return {}

        model_most_recent: Dict[str, Any] = {}
        for f in all_files:
            if f.model_id not in model_most_recent:
                model_most_recent[f.model_id] = f
            elif f.time_data and f.time_data.created:
                existing = model_most_recent[f.model_id]
                existing_time = (
                    existing.time_data.created
                    if existing.time_data and existing.time_data.created
                    else 0
                )
                if f.time_data.created > existing_time:
                    model_most_recent[f.model_id] = f

        result = {}
        default_context_window = 200000

        for model_id, recent_file in model_most_recent.items():
            pricing = self._lookup_pricing_for_file(recent_file)
            if pricing is not None:
                context_window = pricing.context_window
            else:
                context_window = default_context_window

            context_size = (
                recent_file.tokens.input
                + recent_file.tokens.cache_read
                + recent_file.tokens.cache_write
            )

            usage_pct = (
                (context_size / context_window) * 100 if context_window > 0 else 0
            )

            result[model_id] = {
                "context_size": context_size,
                "context_window": context_window,
                "usage_percentage": min(100.0, usage_pct),
            }

        return result

    def validate_monitoring_setup(
        self, base_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate that monitoring can be set up properly.

        Args:
            base_path: Path to directory containing sessions (optional, for legacy mode)

        Returns:
            Validation results
        """
        issues = []
        warnings = []
        info = {}

        # First check for SQLite database (v1.2.0+)
        db_path = SQLiteProcessor.find_database_path()
        if db_path:
            stats = SQLiteProcessor.get_database_stats(db_path)
            if stats.get("exists"):
                info["sqlite"] = {
                    "available": True,
                    "path": str(db_path),
                    "sessions": stats.get("session_count", 0),
                    "sub_agents": stats.get("sub_agent_count", 0),
                }
            else:
                warnings.append("SQLite database found but cannot read stats")
        else:
            info["sqlite"] = {"available": False}

        # Check for file-based storage (legacy)
        base_path = base_path or (
            self.paths_config.messages_dir if self.paths_config else None
        )
        if base_path:
            base_path_obj = Path(base_path)
            if base_path_obj.exists() and base_path_obj.is_dir():
                session_dirs = FileProcessor.find_session_directories(base_path)
                if session_dirs:
                    info["files"] = {
                        "available": True,
                        "path": str(base_path),
                        "sessions": len(session_dirs),
                    }
                else:
                    info["files"] = {
                        "available": True,
                        "path": str(base_path),
                        "sessions": 0,
                    }
            else:
                info["files"] = {"available": False}
        else:
            info["files"] = {"available": False}

        # Check pricing data
        if not self.pricing_data:
            zero_cost = (
                self.currency_converter.format(Decimal("0"))
                if self.currency_converter
                else "$0.00"
            )
            warnings.append(
                f"No pricing data available - costs will show as {zero_cost}"
            )

        # Determine if at least one source is available
        if not info["sqlite"]["available"] and not info["files"].get("available"):
            issues.append(
                "No session data source found. Expected SQLite database or file storage."
            )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "info": info,
        }
