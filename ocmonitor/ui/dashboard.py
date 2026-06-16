"""Live dashboard UI components for OpenCode Monitor."""

import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..models.session import SessionData
from ..models.tool_usage import ToolUsageStats, ModelToolUsage
from ..models.workflow import SessionWorkflow
from ..utils.formatting import ColorFormatter
from ..utils.time_utils import TimeUtils


class DashboardUI:
    """UI components for the live dashboard."""

    def __init__(self, console: Optional[Console] = None, currency_converter=None):
        """Initialize dashboard UI.

        Args:
            console: Rich console instance. If None, creates a new one.
            currency_converter: Optional CurrencyConverter for currency formatting.
        """
        self.console = console or Console()
        self.currency_converter = currency_converter

    def _fmt_cost(self, amount: Decimal) -> str:
        """Format cost amount using currency converter."""
        if self.currency_converter:
            return self.currency_converter.format(amount)
        return f"${amount:.2f}"

    def _flash_style(
        self,
        field_name: str,
        changed_fields: Optional[Set[str]],
        base_style: str,
        flash_style: str,
    ) -> str:
        """Return flash style if field changed, else base style.

        Args:
            field_name: Semantic field name (e.g., "tokens.input", "cost.total")
            changed_fields: Set of changed field names from ValueChangeTracker
            base_style: Normal Rich theme style (e.g., "metric.tokens")
            flash_style: Highlight Rich theme style (e.g., "metric.flash.tokens")

        Returns:
            The appropriate style string
        """
        if changed_fields and field_name in changed_fields:
            return flash_style
        return base_style

    def create_header(
        self,
        session: SessionData,
        workflow: Optional[SessionWorkflow] = None,
        controls_hint: Optional[str] = None,
        current_time: Optional[datetime] = None,
    ) -> Panel:
        """Create header panel with session info."""
        if current_time is None:
            current_time = datetime.now()
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")

        if workflow and workflow.has_sub_agents:
            # Show workflow info with sub-agent count
            header_text = (
                f"[dashboard.header]OpenCode Live Dashboard[/dashboard.header]  "
                f"[metric.label]Project:[/metric.label] [dashboard.project]{workflow.project_name}[/dashboard.project]  "
                f"[metric.label]Session:[/metric.label] [dashboard.session]{workflow.display_title}[/dashboard.session]  "
                f"[metric.label]Updated:[/metric.label] [metric.value]{current_time_str}[/metric.value]  "
                f"[metric.label]Workflow:[/metric.label] [dashboard.info]{workflow.session_count} sessions[/dashboard.info] "
                f"[metric.label]([/metric.label][metric.value]1 main + {workflow.sub_agent_count} sub[/metric.value][metric.label])[/metric.label]"
            )
        else:
            header_text = (
                f"[dashboard.header]OpenCode Live Dashboard[/dashboard.header]  "
                f"[metric.label]Project:[/metric.label] [dashboard.project]{session.project_name}[/dashboard.project]  "
                f"[metric.label]Session:[/metric.label] [dashboard.session]{session.display_title}[/dashboard.session]  "
                f"[metric.label]Updated:[/metric.label] [metric.value]{current_time_str}[/metric.value]  "
                f"[metric.label]Interactions:[/metric.label] [metric.value]{session.interaction_count}[/metric.value]"
            )

        return Panel(
            header_text,
            title=Text("Dashboard", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_controls_panel(self, controls_hint: str) -> Panel:
        """Create dedicated controls panel for live keybind hints."""
        controls_text = f"[dim]{controls_hint}[/dim]"
        return Panel(
            controls_text,
            title=Text("Controls", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_token_panel(
        self, session: SessionData, recent_file: Optional[Any] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create token consumption panel."""
        session_tokens = session.total_tokens

        ri_s = self._flash_style("tokens.input", changed_fields, "metric.value", "metric.flash.tokens")
        ro_s = self._flash_style("tokens.output", changed_fields, "metric.value", "metric.flash.tokens")
        rcw_s = self._flash_style("tokens.cache_write", changed_fields, "metric.value", "metric.flash.tokens")
        rcr_s = self._flash_style("tokens.cache_read", changed_fields, "metric.value", "metric.flash.tokens")
        si_s = self._flash_style("tokens.input", changed_fields, "metric.value", "metric.flash.tokens")
        so_s = self._flash_style("tokens.output", changed_fields, "metric.value", "metric.flash.tokens")
        scw_s = self._flash_style("tokens.cache_write", changed_fields, "metric.value", "metric.flash.tokens")
        scr_s = self._flash_style("tokens.cache_read", changed_fields, "metric.value", "metric.flash.tokens")
        tot_s = self._flash_style("tokens.total", changed_fields, "metric.tokens", "metric.flash.tokens")

        # Create compact horizontal layout
        if recent_file:
            token_text = (
                f"[dashboard.header]Recent Interaction[/dashboard.header]\n"
                f"[metric.label]Input:[/metric.label] [{ri_s}]{recent_file.tokens.input:,}[/{ri_s}]    "
                f"[metric.label]Cache W:[/metric.label] [{rcw_s}]{recent_file.tokens.cache_write:,}[/{rcw_s}]\n"
                f"[metric.label]Output:[/metric.label] [{ro_s}]{recent_file.tokens.output:,}[/{ro_s}]   "
                f"[metric.label]Cache R:[/metric.label] [{rcr_s}]{recent_file.tokens.cache_read:,}[/{rcr_s}]\n\n"
                f"[dashboard.header]Session Totals[/dashboard.header]\n"
                f"[metric.label]Input:[/metric.label] [{si_s}]{session_tokens.input:,}[/{si_s}]    "
                f"[metric.label]Cache W:[/metric.label] [{scw_s}]{session_tokens.cache_write:,}[/{scw_s}]\n"
                f"[metric.label]Output:[/metric.label] [{so_s}]{session_tokens.output:,}[/{so_s}]   "
                f"[metric.label]Cache R:[/metric.label] [{scr_s}]{session_tokens.cache_read:,}[/{scr_s}]\n"
                f"[metric.label]Total:[/metric.label] [{tot_s}]{session_tokens.total:,}[/{tot_s}]"
            )
        else:
            token_text = (
                f"[dashboard.header]Session Totals[/dashboard.header]\n"
                f"[metric.label]Input:[/metric.label] [{si_s}]{session_tokens.input:,}[/{si_s}]    "
                f"[metric.label]Cache W:[/metric.label] [{scw_s}]{session_tokens.cache_write:,}[/{scw_s}]\n"
                f"[metric.label]Output:[/metric.label] [{so_s}]{session_tokens.output:,}[/{so_s}]   "
                f"[metric.label]Cache R:[/metric.label] [{scr_s}]{session_tokens.cache_read:,}[/{scr_s}]\n"
                f"[metric.label]Total:[/metric.label] [{tot_s}]{session_tokens.total:,}[/{tot_s}]"
            )

        return Panel(
            token_text,
            title=Text("Tokens", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_cost_panel(
        self,
        session: SessionData,
        pricing_data: Dict[str, Any],
        quota: Optional[Decimal] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create cost tracking panel."""
        total_cost = session.calculate_total_cost(pricing_data)
        cost_s = self._flash_style("cost.total", changed_fields, "metric.cost", "metric.flash.cost")

        if quota:
            percentage = min(100, float(total_cost / quota) * 100)
            progress_bar = self.create_compact_progress_bar(percentage)
            cost_color = self.get_cost_color(percentage)

            cost_text = (
                f"[dashboard.header]Cost Tracking[/dashboard.header]\n"
                f"[metric.label]Session:[/metric.label] [{cost_s}]{self._fmt_cost(total_cost)}[/{cost_s}]\n"
                f"[metric.label]Quota:[/metric.label] [metric.cost]{self._fmt_cost(quota)}[/metric.cost]\n"
                f"[{cost_color}]{progress_bar}[/{cost_color}]"
            )
        else:
            cost_text = (
                f"[dashboard.header]Cost Tracking[/dashboard.header]\n"
                f"[metric.label]Session:[/metric.label] [{cost_s}]{self._fmt_cost(total_cost)}[/{cost_s}]\n"
                f"[metric.label]No quota configured[/metric.label]"
            )

        return Panel(
            cost_text,
            title=Text("Cost", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_model_panel(
        self,
        session: SessionData,
        pricing_data: Dict[str, Any],
        per_model_output_rates: Optional[Dict[str, float]] = None,
        per_model_context: Optional[Dict[str, Dict[str, Any]]] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create model usage panel."""
        model_breakdown = session.get_model_breakdown(pricing_data)
        per_model_output_rates = per_model_output_rates or {}
        per_model_context = per_model_context or {}

        if not model_breakdown:
            return Panel(
                "[metric.label]No model data available[/metric.label]",
                title=Text("Models", style="dashboard.title"),
                border_style="dashboard.border",
            )

        model_lines = []
        for model, stats in model_breakdown.items():
            model_name = model[:35] + "..." if len(model) > 38 else model
            model_key = f"model.{model}"
            
            tokens_style = self._flash_style(
                f"{model_key}.tokens", changed_fields, "metric.value", "metric.flash.tokens"
            )
            cost_style = self._flash_style(
                f"{model_key}.cost", changed_fields, "metric.cost", "metric.flash.cost"
            )
            
            context_info = per_model_context.get(model, {})
            context_pct = context_info.get("usage_percentage", 0.0)
            context_bar = self.create_compact_progress_bar(context_pct, 8)
            
            output_rate = per_model_output_rates.get(model, 0.0)
            rate_str = f" - {output_rate:.1f} tok/s" if output_rate > 0 else ""
            
            model_lines.append(
                f"[metric.label]{model_name}[/metric.label]  -  "
                f"[{tokens_style}]{stats['tokens'].total:,}[/{tokens_style}] [metric.tokens]tok[/metric.tokens]  "
                f"[{cost_style}]{self._fmt_cost(stats['cost'])}[/{cost_style}]  -  "
                f"context {context_bar}{rate_str}"
            )

        model_text = "\n".join(model_lines)

        return Panel(
            model_text,
            title=Text("Models", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_context_panel(
        self, recent_file: Optional[Any], context_window: int = 200000,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create context window status panel."""
        if not recent_file:
            return Panel(
                "[metric.label]No recent interaction[/metric.label]",
                title=Text("Context", style="dashboard.title"),
                border_style="dashboard.border",
            )

        # Calculate context size (input + cache read + cache write from most recent)
        context_size = (
            recent_file.tokens.input
            + recent_file.tokens.cache_read
            + recent_file.tokens.cache_write
        )

        percentage = min(100, (context_size / context_window) * 100)
        progress_bar = self.create_compact_progress_bar(percentage, 12)
        context_color = self.get_context_color(percentage)
        cs_s = self._flash_style("context_size", changed_fields, "metric.value", "metric.flash")
        cw_s = self._flash_style("context_window", changed_fields, "metric.value", "metric.flash")

        context_text = (
            f"[metric.label]Size:[/metric.label] [{cs_s}]{context_size:,}[/{cs_s}]\n"
            f"[metric.label]Window:[/metric.label] [{cw_s}]{context_window:,}[/{cw_s}]\n"
            f"[{context_color}]{progress_bar}[/{context_color}]"
        )

        return Panel(
            context_text,
            title=Text("Context", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_burn_rate_panel(self, burn_rate: float, changed_fields: Optional[Set[str]] = None) -> Panel:
        """Create output token rate panel (tokens per second)."""
        br_s = self._flash_style("burn_rate", changed_fields, "metric.value", "metric.flash")
        if burn_rate == 0:
            burn_text = "[metric.label]No recent activity[/metric.label]"
        else:
            # Add level indicator
            if burn_rate > 90:
                level = "[status.error]VERY FAST[/status.error]"
            elif burn_rate > 60:
                level = "[status.info]FAST[/status.info]"
            elif burn_rate >= 25:
                level = "[status.warning]MEDIUM[/status.warning]"
            else:
                level = "[status.success]SLOW[/status.success]"

            burn_text = (
                f"[{br_s}]{burn_rate:,.1f}[/{br_s}] [metric.tokens]tok/sec[/metric.tokens]\n"
                f"{level}"
            )

        return Panel(
            burn_text,
            title=Text("Output Rate", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_session_time_panel(
        self,
        session: SessionData,
        current_time: Optional[datetime] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create session time progress panel with 5-hour maximum."""
        if not session.start_time:
            return Panel(
                "[metric.label]No session timing data[/metric.label]",
                title=Text("Session Time", style="dashboard.title"),
                border_style="dashboard.border",
            )

        # Calculate duration from start_time to now (updates continuously even when idle)
        if current_time is None:
            current_time = datetime.now()
        session_duration = current_time - session.start_time
        duration_ms = int(session_duration.total_seconds() * 1000)

        # Calculate percentage based on 5-hour maximum
        max_hours = 5.0
        duration_hours = session_duration.total_seconds() / 3600
        percentage = min(100.0, (duration_hours / max_hours) * 100.0)

        # Format duration display using hours and minutes format
        duration_display = TimeUtils.format_duration_hm(duration_ms)

        # Create progress bar with time-based colors
        progress_bar = self.create_compact_progress_bar(percentage, 12)
        time_color = self.get_time_color(percentage)
        dur_s = self._flash_style("duration_ms", changed_fields, "metric.value", "metric.flash")

        time_text = (
            f"[metric.label]Duration:[/metric.label] [{dur_s}]{duration_display}[/{dur_s}]\n"
            f"[metric.label]Max:[/metric.label] [metric.value]{max_hours:.0f}h[/metric.value]\n"
            f"[{time_color}]{progress_bar}[/{time_color}]"
        )

        return Panel(
            time_text,
            title=Text("Session Time", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_status_panel(
        self,
        session: SessionData,
        pricing_data: Dict[str, Any],
        quota: Optional[Decimal] = None,
        current_time: Optional[datetime] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create combined status panel with Cost + Session Time."""
        # --- Cost section ---
        total_cost = session.calculate_total_cost(pricing_data)
        cost_s = self._flash_style("cost.total", changed_fields, "metric.cost", "metric.flash.cost")

        if quota:
            percentage = min(100, float(total_cost / quota) * 100)
            progress_bar = self.create_compact_progress_bar(percentage, 10)
            cost_color = self.get_cost_color(percentage)
            cost_section = (
                f"[dashboard.header]Cost[/dashboard.header]\n"
                f"[metric.label]Session:[/metric.label] [{cost_s}]{self._fmt_cost(total_cost)}[/{cost_s}]  "
                f"[metric.label]Quota:[/metric.label] [metric.cost]{self._fmt_cost(quota)}[/metric.cost]\n"
                f"[{cost_color}]{progress_bar}[/{cost_color}]"
            )
        else:
            cost_section = (
                f"[dashboard.header]Cost[/dashboard.header]\n"
                f"[metric.label]Session:[/metric.label] [{cost_s}]{self._fmt_cost(total_cost)}[/{cost_s}]  "
                f"[dim]No quota[/dim]"
            )

        # --- Time section ---
        if session.start_time:
            if current_time is None:
                current_time = datetime.now()
            session_duration = current_time - session.start_time
            duration_ms = int(session_duration.total_seconds() * 1000)
            max_hours = 5.0
            duration_hours = session_duration.total_seconds() / 3600
            percentage = min(100.0, (duration_hours / max_hours) * 100.0)
            duration_display = TimeUtils.format_duration_hm(duration_ms)
            progress_bar = self.create_compact_progress_bar(percentage, 10)
            time_color = self.get_time_color(percentage)
            dur_s = self._flash_style("duration_ms", changed_fields, "metric.value", "metric.flash")
            time_section = (
                f"[dashboard.header]Time[/dashboard.header]\n"
                f"[metric.label]Duration:[/metric.label] [{dur_s}]{duration_display}[/{dur_s}]  "
                f"[metric.label]Max:[/metric.label] [metric.value]{max_hours:.0f}h[/metric.value]\n"
                f"[{time_color}]{progress_bar}[/{time_color}]"
            )
        else:
            time_section = (
                f"[dashboard.header]Time[/dashboard.header]\n"
                f"[dim]No timing data[/dim]"
            )

        status_text = (
            f"{cost_section}\n"
            f"[dashboard.border]{'─' * 24}[/dashboard.border]\n"
            f"{time_section}"
        )

        return Panel(
            status_text,
            title=Text("Status", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_workflow_status_panel(
        self,
        workflow: SessionWorkflow,
        pricing_data: Dict[str, Any],
        quota: Optional[Decimal] = None,
        current_time: Optional[datetime] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create combined status panel with Workflow Cost + Workflow Time."""
        # --- Cost section ---
        total_cost = workflow.calculate_total_cost(pricing_data)
        cost_s = self._flash_style("cost.total", changed_fields, "metric.cost", "metric.flash.cost")

        if quota:
            percentage = min(100, float(total_cost / quota) * 100)
            progress_bar = self.create_compact_progress_bar(percentage, 10)
            cost_color = self.get_cost_color(percentage)
            cost_section = (
                f"[dashboard.header]Cost[/dashboard.header]\n"
                f"[metric.label]Total:[/metric.label] [{cost_s}]{self._fmt_cost(total_cost)}[/{cost_s}]  "
                f"[metric.label]Quota:[/metric.label] [metric.cost]{self._fmt_cost(quota)}[/metric.cost]\n"
                f"[{cost_color}]{progress_bar}[/{cost_color}]"
            )
        else:
            cost_section = (
                f"[dashboard.header]Cost[/dashboard.header]\n"
                f"[metric.label]Total:[/metric.label] [{cost_s}]{self._fmt_cost(total_cost)}[/{cost_s}]  "
                f"[dim]No quota[/dim]"
            )

        # --- Time section ---
        if workflow.start_time:
            if current_time is None:
                current_time = datetime.now()
            workflow_duration = current_time - workflow.start_time
            duration_ms = int(workflow_duration.total_seconds() * 1000)
            max_hours = 5.0
            duration_hours = workflow_duration.total_seconds() / 3600
            percentage = min(100.0, (duration_hours / max_hours) * 100.0)
            duration_display = TimeUtils.format_duration_hm(duration_ms)
            progress_bar = self.create_compact_progress_bar(percentage, 10)
            time_color = self.get_time_color(percentage)
            dur_s = self._flash_style("duration_ms", changed_fields, "metric.value", "metric.flash")
            time_section = (
                f"[dashboard.header]Time[/dashboard.header]\n"
                f"[metric.label]Duration:[/metric.label] [{dur_s}]{duration_display}[/{dur_s}]  "
                f"[metric.label]Max:[/metric.label] [metric.value]{max_hours:.0f}h[/metric.value]\n"
                f"[{time_color}]{progress_bar}[/{time_color}]"
            )
        else:
            time_section = (
                f"[dashboard.header]Time[/dashboard.header]\n"
                f"[dim]No timing data[/dim]"
            )

        status_text = (
            f"{cost_section}\n"
            f"[dashboard.border]{'─' * 24}[/dashboard.border]\n"
            f"{time_section}"
        )

        return Panel(
            status_text,
            title=Text("Status", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_recent_file_panel(self, recent_file: Optional[Any]) -> Panel:
        """Create recent file info panel."""
        if not recent_file:
            return Panel(
                "[metric.label]No recent files[/metric.label]",
                title=Text("Recent", style="dashboard.title"),
                border_style="dashboard.border",
            )

        # Truncate file name if too long
        file_name = recent_file.file_name
        if len(file_name) > 20:
            file_name = "..." + file_name[-17:]

        file_text = (
            f"[metric.label]File:[/metric.label] [metric.value]{file_name}[/metric.value]\n"
            f"[metric.label]Model:[/metric.label] [metric.value]{recent_file.model_id[:35]}[/metric.value]"
        )

        if recent_file.time_data and recent_file.time_data.duration_ms:
            duration = self.format_duration(recent_file.time_data.duration_ms)
            file_text += f"\n[metric.label]Duration:[/metric.label] [metric.value]{duration}[/metric.value]"

        return Panel(
            file_text,
            title=Text("Recent", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_tool_panel(
        self, tool_stats: List[ToolUsageStats], max_tools: int = 10
    ) -> Panel:
        """Create tool usage panel showing success/failure statistics.

        Args:
            tool_stats: List of tool usage statistics
            max_tools: Maximum number of tools to display

        Returns:
            Panel with tool usage information
        """
        if not tool_stats:
            return Panel(
                "[metric.label]No tool activity yet[/metric.label]",
                title=Text("Tools", style="dashboard.title"),
                title_align="left",
                border_style="dashboard.border",
            )

        lines = []
        for stat in tool_stats[:max_tools]:
            tool_name = stat.tool_name
            if len(tool_name) > 12:
                tool_name = tool_name[:9] + "..."

            success_rate = stat.success_rate
            bar = self.create_compact_progress_bar(success_rate, 10)
            color = self.get_tool_color(success_rate)

            lines.append(
                f"[metric.label]{tool_name:<12}[/metric.label] "
                f"[metric.value]{stat.total_calls:>4}[/metric.value] "
                f"[{color}]{bar}[/{color}]"
            )

        tool_text = "\n".join(lines)

        return Panel(
            tool_text,
            title=Text("Tools", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def get_tool_color(self, success_rate: float) -> str:
        """Get color for tool success rate.

        Args:
            success_rate: Success rate percentage

        Returns:
            Color string for styling
        """
        if success_rate >= 90:
            return "status.success"
        elif success_rate >= 70:
            return "status.warning"
        else:
            return "status.error"

    def create_model_tool_panel(
        self,
        model_tool_usage: ModelToolUsage,
        max_tools: int = 15,
        model_tokens: Optional[int] = None,
        model_cost: Optional[Decimal] = None,
        context_pct: Optional[float] = None,
        output_rate: Optional[float] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create a panel showing tool usage for a single model.

        Args:
            model_tool_usage: ModelToolUsage containing model name and tool stats
            max_tools: Maximum number of tools to display
            model_tokens: Optional token count for this model to display in header
            model_cost: Optional cost for this model to display in header
            context_pct: Optional context usage percentage for this model
            output_rate: Optional output rate (tok/sec) for this model
            changed_fields: Optional set of changed field names for flash highlighting

        Returns:
            Panel with tool usage information for this model
        """
        model_name = model_tool_usage.model_name
        if len(model_name) > 35:
            model_name = model_name[:32] + "..."

        tool_stats = model_tool_usage.tool_stats[:max_tools]

        if not tool_stats:
            return Panel(
                "[metric.label]No tool activity[/metric.label]",
                title=Text(model_name, style="dashboard.title"),
                title_align="left",
                border_style="dashboard.border",
            )

        lines = []

        if model_tokens is not None:
            model_key = f"model.{model_tool_usage.model_name}"
            tokens_style = self._flash_style(
                f"{model_key}.tokens", changed_fields, "metric.value", "metric.flash.tokens"
            )
            cost_style = self._flash_style(
                f"{model_key}.cost", changed_fields, "metric.cost", "metric.flash.cost"
            )
            cost_str = f" [{cost_style}]{self._fmt_cost(model_cost)}[/{cost_style}]" if model_cost is not None else ""

            # Add context and output rate info
            extra_info = []
            if context_pct is not None:
                context_bar = self.create_compact_progress_bar(context_pct, 8)
                extra_info.append(f"context {context_bar}")
            if output_rate is not None and output_rate > 0:
                extra_info.append(f"{output_rate:.1f} tok/s")

            extra_str = "  " + "  ".join(extra_info) if extra_info else ""

            lines.append(
                f"[{tokens_style}]{model_tokens:,}[/{tokens_style}] [metric.tokens]tokens[/metric.tokens]{cost_str}{extra_str}"
            )
            lines.append("[dashboard.border]────────────────────────[/dashboard.border]")

        for stat in tool_stats:
            tool_name = stat.tool_name
            if len(tool_name) > 12:
                tool_name = tool_name[:9] + "..."

            success_rate = stat.success_rate
            bar = self.create_compact_progress_bar(success_rate, 8)
            color = self.get_tool_color(success_rate)

            lines.append(
                f"[metric.label]{tool_name:<12}[/metric.label] "
                f"[metric.value]{stat.total_calls:>3}[/metric.value] "
                f"[{color}]{bar}[/{color}]"
            )

        tool_text = "\n".join(lines)

        return Panel(
            tool_text,
            title=Text(model_name, style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_tool_grid_panel(
        self,
        tool_stats_by_model: List[ModelToolUsage],
        model_breakdown: Optional[Dict[str, Dict[str, Any]]] = None,
        per_model_output_rates: Optional[Dict[str, float]] = None,
        per_model_context: Optional[Dict[str, Dict[str, Any]]] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Layout:
        """Create a 2-column grid layout for per-model tool panels.

        Args:
            tool_stats_by_model: List of ModelToolUsage (one per model)
            model_breakdown: Optional dict mapping model names to token/cost data
            per_model_output_rates: Optional dict mapping model to output rate
            per_model_context: Optional dict mapping model to context info
            changed_fields: Optional set of changed field names for flash highlighting

        Returns:
            Layout containing the grid of model tool panels
        """
        if not tool_stats_by_model:
            return Layout(
                Panel(
                    "[metric.label]No tool activity yet[/metric.label]",
                    title=Text("Tools", style="dashboard.title"),
                    title_align="left",
                    border_style="dashboard.border",
                )
            )

        if model_breakdown is None:
            model_breakdown = {}
        per_model_output_rates = per_model_output_rates or {}
        per_model_context = per_model_context or {}

        def get_model_info(model_name: str):
            """Return tokens, cost, context usage, and output rate for a model."""
            if model_name in model_breakdown:
                stats = model_breakdown[model_name]
                tokens = stats.get("tokens", {}).total if hasattr(stats.get("tokens", {}), "total") else stats.get("tokens", 0)
                cost = stats.get("cost")
            else:
                tokens, cost = None, None
            
            context_info = per_model_context.get(model_name, {})
            context_pct = context_info.get("usage_percentage")
            output_rate = per_model_output_rates.get(model_name, 0.0)
            
            return tokens, cost, context_pct, output_rate

        left_models = []
        right_models = []
        for i, model_usage in enumerate(tool_stats_by_model):
            if i % 2 == 0:
                left_models.append(model_usage)
            else:
                right_models.append(model_usage)

        left_panels = []
        for model_usage in left_models:
            model_tokens, model_cost, context_pct, output_rate = get_model_info(model_usage.model_name)
            left_panels.append(self.create_model_tool_panel(
                model_usage, model_tokens=model_tokens, model_cost=model_cost,
                context_pct=context_pct, output_rate=output_rate,
                changed_fields=changed_fields
            ))

        right_panels = []
        for model_usage in right_models:
            model_tokens, model_cost, context_pct, output_rate = get_model_info(model_usage.model_name)
            right_panels.append(self.create_model_tool_panel(
                model_usage, model_tokens=model_tokens, model_cost=model_cost,
                context_pct=context_pct, output_rate=output_rate,
                changed_fields=changed_fields
            ))

        left_column = Layout()
        if left_panels:
            left_column.split_column(*[Layout(p, ratio=1) for p in left_panels])

        right_column = Layout()
        if right_panels:
            right_column.split_column(*[Layout(p, ratio=1) for p in right_panels])

        grid_layout = Layout()
        if left_panels and right_panels:
            grid_layout.split_row(left_column, right_column)
        elif left_panels:
            grid_layout.split_column(left_column)
        elif right_panels:
            grid_layout.split_column(right_column)

        outer_panel = Panel(
            grid_layout,
            title=Text("Tools", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

        return Layout(outer_panel)

    def create_dashboard_layout(
        self,
        session: SessionData,
        recent_file: Optional[Any],
        pricing_data: Dict[str, Any],
        quota: Optional[Decimal] = None,
        per_model_output_rates: Optional[Dict[str, float]] = None,
        per_model_context: Optional[Dict[str, Dict[str, Any]]] = None,
        workflow: Optional[SessionWorkflow] = None,
        tool_stats: Optional[List[ToolUsageStats]] = None,
        tool_stats_by_model: Optional[List[ModelToolUsage]] = None,
        controls_hint: Optional[str] = None,
        current_time: Optional[datetime] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Layout:
        """Create the complete dashboard layout."""
        if current_time is None:
            current_time = datetime.now()
        layout = Layout()

        # Default empty dicts if not provided
        per_model_output_rates = per_model_output_rates or {}
        per_model_context = per_model_context or {}

        # Use workflow data if available, otherwise use session data
        if workflow and workflow.has_sub_agents:
            # Create panels using workflow totals
            header = self.create_header(session, workflow, current_time=current_time)
            token_panel = self.create_workflow_token_panel(workflow, recent_file, changed_fields=changed_fields)
            status_panel = self.create_workflow_status_panel(workflow, pricing_data, quota, current_time=current_time, changed_fields=changed_fields)
            model_panel = self.create_workflow_model_panel(
                workflow, pricing_data, per_model_output_rates, per_model_context, changed_fields=changed_fields
            )
        else:
            # Create panels using single session data
            header = self.create_header(session, current_time=current_time)
            token_panel = self.create_token_panel(session, recent_file, changed_fields=changed_fields)
            status_panel = self.create_status_panel(session, pricing_data, quota, current_time=current_time, changed_fields=changed_fields)
            model_panel = self.create_model_panel(
                session, pricing_data, per_model_output_rates, per_model_context, changed_fields=changed_fields
            )

        recent_file_panel = self.create_recent_file_panel(recent_file)

        # Determine which tool display to use based on model count
        by_model = tool_stats_by_model or []
        use_grid = len(by_model) > 1

        # Build model breakdown data for passing to tool grid panels
        model_breakdown: Optional[Dict[str, Dict[str, Any]]] = None
        if use_grid:
            if workflow and workflow.has_sub_agents:
                from collections import defaultdict
                model_breakdown = defaultdict(lambda: {"tokens": 0, "cost": Decimal("0.0")})
                for sess in workflow.all_sessions:
                    sess_breakdown = sess.get_model_breakdown(pricing_data)
                    for model, stats in sess_breakdown.items():
                        model_breakdown[model]["tokens"] += stats["tokens"].total
                        model_breakdown[model]["cost"] += stats["cost"]
                model_breakdown = dict(model_breakdown)
            else:
                model_breakdown = session.get_model_breakdown(pricing_data)

        # Initialize variables
        tool_grid_panel: Optional[Layout] = None
        tool_panel: Optional[Panel] = None
        model_ratio = 3
        tool_ratio = 2

        if use_grid:
            tool_grid_panel = self.create_tool_grid_panel(
                by_model,
                model_breakdown=model_breakdown,
                per_model_output_rates=per_model_output_rates,
                per_model_context=per_model_context,
                changed_fields=changed_fields,
            )
            model_ratio = 2
            tool_ratio = 3
        else:
            flat_tool_stats = tool_stats or []
            if by_model and not tool_stats:
                flat_tool_stats = by_model[0].tool_stats
            tool_panel = self.create_tool_panel(flat_tool_stats)

        # 3-4 section layout: Header, Metrics, Models+Tools, optional Controls (bottom)
        if controls_hint:
            controls_panel = self.create_controls_panel(controls_hint)
            layout.split_column(
                Layout(header, size=3),  # Compact header
                Layout(name="metrics", size=12),  # Tokens + Status + Recent (single row)
                Layout(name="models_tools", minimum_size=4),  # Model + Tool breakdown
                Layout(controls_panel, size=3),  # Persistent keybind visibility
            )
        else:
            layout.split_column(
                Layout(header, size=3),  # Compact header
                Layout(name="metrics", size=12),  # Tokens + Status + Recent (single row)
                Layout(name="models_tools", minimum_size=4),  # Model + Tool breakdown
            )

        # Metrics section: 3-column layout (Tokens 50% | Status 25% | Recent 25%)
        layout["metrics"].split_row(
            Layout(token_panel, ratio=2),  # 50% - token data (most content)
            Layout(status_panel, ratio=1),  # 25% - cost + time combined
            Layout(recent_file_panel, ratio=1),  # 25% - recent file info
        )

        # Models + Tools section: Full width to tools when using grid (model info embedded in tool panels)
        if use_grid:
            assert tool_grid_panel is not None
            layout["models_tools"].split_column(tool_grid_panel)
        else:
            assert tool_panel is not None
            layout["models_tools"].split_row(
                Layout(model_panel, ratio=model_ratio),
                Layout(tool_panel, ratio=tool_ratio),
            )

        return layout

    def create_progress_bar(self, percentage: float, width: int = 30) -> str:
        """Create a text-based progress bar."""
        filled = int(width * percentage / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {percentage:.1f}%"

    def create_compact_progress_bar(self, percentage: float, width: int = 20) -> str:
        """Create a compact progress bar for space-efficient display."""
        filled = int(width * percentage / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"{bar} {percentage:.0f}%"

    def get_cost_color(self, percentage: float) -> str:
        """Get color for cost based on percentage."""
        return ColorFormatter.get_color_by_percentage(percentage)

    def get_context_color(self, percentage: float) -> str:
        """Get color for context window based on percentage."""
        return ColorFormatter.get_color_by_percentage(percentage)

    def get_time_color(self, percentage: float) -> str:
        """Get color for session time based on percentage of 5-hour max."""
        return ColorFormatter.get_color_by_percentage(percentage)

    def format_duration(self, milliseconds: int) -> str:
        """Format duration in milliseconds to hours and minutes format."""
        return TimeUtils.format_duration_hm(milliseconds)

    def clear_screen(self):
        """Clear the terminal screen."""
        os.system("cls" if os.name == "nt" else "clear")

    def create_simple_table(self, data: Dict[str, Any]) -> Table:
        """Create a simple data table for fallback rendering."""
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="metric.important")
        table.add_column("Value", style="metric.value")

        for key, value in data.items():
            table.add_row(key, str(value))

        return table

    def create_workflow_token_panel(
        self, workflow: SessionWorkflow, recent_file: Optional[Any] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create token consumption panel for workflow."""
        workflow_tokens = workflow.total_tokens

        ri_s = self._flash_style("tokens.input", changed_fields, "metric.value", "metric.flash.tokens")
        ro_s = self._flash_style("tokens.output", changed_fields, "metric.value", "metric.flash.tokens")
        rcw_s = self._flash_style("tokens.cache_write", changed_fields, "metric.value", "metric.flash.tokens")
        rcr_s = self._flash_style("tokens.cache_read", changed_fields, "metric.value", "metric.flash.tokens")
        wi_s = self._flash_style("tokens.input", changed_fields, "metric.value", "metric.flash.tokens")
        wo_s = self._flash_style("tokens.output", changed_fields, "metric.value", "metric.flash.tokens")
        wcw_s = self._flash_style("tokens.cache_write", changed_fields, "metric.value", "metric.flash.tokens")
        wcr_s = self._flash_style("tokens.cache_read", changed_fields, "metric.value", "metric.flash.tokens")
        tot_s = self._flash_style("tokens.total", changed_fields, "metric.tokens", "metric.flash.tokens")

        # Create compact horizontal layout showing workflow totals
        if recent_file:
            token_text = (
                f"[dashboard.header]Recent Interaction[/dashboard.header]\n"
                f"[metric.label]Input:[/metric.label] [{ri_s}]{recent_file.tokens.input:,}[/{ri_s}]    "
                f"[metric.label]Cache W:[/metric.label] [{rcw_s}]{recent_file.tokens.cache_write:,}[/{rcw_s}]\n"
                f"[metric.label]Output:[/metric.label] [{ro_s}]{recent_file.tokens.output:,}[/{ro_s}]   "
                f"[metric.label]Cache R:[/metric.label] [{rcr_s}]{recent_file.tokens.cache_read:,}[/{rcr_s}]\n\n"
                f"[dashboard.header]Workflow Totals[/dashboard.header] [metric.label]({workflow.session_count} sessions)[/metric.label]\n"
                f"[metric.label]Input:[/metric.label] [{wi_s}]{workflow_tokens.input:,}[/{wi_s}]    "
                f"[metric.label]Cache W:[/metric.label] [{wcw_s}]{workflow_tokens.cache_write:,}[/{wcw_s}]\n"
                f"[metric.label]Output:[/metric.label] [{wo_s}]{workflow_tokens.output:,}[/{wo_s}]   "
                f"[metric.label]Cache R:[/metric.label] [{wcr_s}]{workflow_tokens.cache_read:,}[/{wcr_s}]\n"
                f"[metric.label]Total:[/metric.label] [{tot_s}]{workflow_tokens.total:,}[/{tot_s}]"
            )
        else:
            token_text = (
                f"[dashboard.header]Workflow Totals[/dashboard.header] [metric.label]({workflow.session_count} sessions)[/metric.label]\n"
                f"[metric.label]Input:[/metric.label] [{wi_s}]{workflow_tokens.input:,}[/{wi_s}]    "
                f"[metric.label]Cache W:[/metric.label] [{wcw_s}]{workflow_tokens.cache_write:,}[/{wcw_s}]\n"
                f"[metric.label]Output:[/metric.label] [{wo_s}]{workflow_tokens.output:,}[/{wo_s}]   "
                f"[metric.label]Cache R:[/metric.label] [{wcr_s}]{workflow_tokens.cache_read:,}[/{wcr_s}]\n"
                f"[metric.label]Total:[/metric.label] [{tot_s}]{workflow_tokens.total:,}[/{tot_s}]"
            )

        return Panel(
            token_text,
            title=Text("Tokens", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_workflow_cost_panel(
        self,
        workflow: SessionWorkflow,
        pricing_data: Dict[str, Any],
        quota: Optional[Decimal] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create cost tracking panel for workflow."""
        total_cost = workflow.calculate_total_cost(pricing_data)
        cost_s = self._flash_style("cost.total", changed_fields, "metric.cost", "metric.flash.cost")

        if quota:
            percentage = min(100, float(total_cost / quota) * 100)
            progress_bar = self.create_compact_progress_bar(percentage)
            cost_color = self.get_cost_color(percentage)

            cost_text = (
                f"[dashboard.header]Workflow Cost[/dashboard.header]\n"
                f"[metric.label]Total:[/metric.label] [{cost_s}]{self._fmt_cost(total_cost)}[/{cost_s}]\n"
                f"[metric.label]Quota:[/metric.label] [metric.cost]{self._fmt_cost(quota)}[/metric.cost]\n"
                f"[{cost_color}]{progress_bar}[/{cost_color}]"
            )
        else:
            cost_text = (
                f"[dashboard.header]Workflow Cost[/dashboard.header]\n"
                f"[metric.label]Total:[/metric.label] [{cost_s}]{self._fmt_cost(total_cost)}[/{cost_s}]\n"
                f"[metric.label]No quota configured[/metric.label]"
            )

        return Panel(
            cost_text,
            title=Text("Cost", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_workflow_model_panel(
        self,
        workflow: SessionWorkflow,
        pricing_data: Dict[str, Any],
        per_model_output_rates: Optional[Dict[str, float]] = None,
        per_model_context: Optional[Dict[str, Dict[str, Any]]] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create model usage panel for workflow."""
        from collections import defaultdict

        per_model_output_rates = per_model_output_rates or {}
        per_model_context = per_model_context or {}

        model_data: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"tokens": 0, "cost": Decimal("0.0")}
        )

        for session in workflow.all_sessions:
            model_breakdown = session.get_model_breakdown(pricing_data)
            for model, stats in model_breakdown.items():
                model_data[model]["tokens"] += stats["tokens"].total
                model_data[model]["cost"] += stats["cost"]

        if not model_data:
            return Panel(
                "[metric.label]No model data available[/metric.label]",
                title=Text("Models", style="dashboard.title"),
                border_style="dashboard.border",
            )

        model_lines = []
        for model, stats in sorted(
            model_data.items(), key=lambda x: x[1]["cost"], reverse=True
        ):
            model_name = model[:35] + "..." if len(model) > 38 else model
            model_key = f"model.{model}"
            
            tokens_style = self._flash_style(
                f"{model_key}.tokens", changed_fields, "metric.value", "metric.flash.tokens"
            )
            cost_style = self._flash_style(
                f"{model_key}.cost", changed_fields, "metric.cost", "metric.flash.cost"
            )
            
            context_info = per_model_context.get(model, {})
            context_pct = context_info.get("usage_percentage", 0.0)
            context_bar = self.create_compact_progress_bar(context_pct, 8)
            
            output_rate = per_model_output_rates.get(model, 0.0)
            rate_str = f" - {output_rate:.1f} tok/s" if output_rate > 0 else ""
            
            model_lines.append(
                f"[metric.label]{model_name}[/metric.label]  -  "
                f"[{tokens_style}]{stats['tokens']:,}[/{tokens_style}] [metric.tokens]tok[/metric.tokens]  "
                f"[{cost_style}]{self._fmt_cost(stats['cost'])}[/{cost_style}]  -  "
                f"context {context_bar}{rate_str}"
            )

        model_text = "\n".join(model_lines)

        return Panel(
            model_text,
            title=Text("Models", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )

    def create_workflow_time_panel(
        self,
        workflow: SessionWorkflow,
        current_time: Optional[datetime] = None,
        changed_fields: Optional[Set[str]] = None,
    ) -> Panel:
        """Create session time progress panel for workflow."""
        if not workflow.start_time:
            return Panel(
                "[metric.label]No workflow timing data[/metric.label]",
                title=Text("Workflow Time", style="dashboard.title"),
                border_style="dashboard.border",
            )

        # Calculate duration from workflow start_time to now
        if current_time is None:
            current_time = datetime.now()
        workflow_duration = current_time - workflow.start_time
        duration_ms = int(workflow_duration.total_seconds() * 1000)

        # Calculate percentage based on 5-hour maximum
        max_hours = 5.0
        duration_hours = workflow_duration.total_seconds() / 3600
        percentage = min(100.0, (duration_hours / max_hours) * 100.0)

        # Format duration display
        duration_display = TimeUtils.format_duration_hm(duration_ms)

        # Create progress bar with time-based colors
        progress_bar = self.create_compact_progress_bar(percentage, 12)
        time_color = self.get_time_color(percentage)
        dur_s = self._flash_style("duration_ms", changed_fields, "metric.value", "metric.flash")

        time_text = (
            f"[metric.label]Duration:[/metric.label] [{dur_s}]{duration_display}[/{dur_s}]\n"
            f"[metric.label]Max:[/metric.label] [metric.value]{max_hours:.0f}h[/metric.value]\n"
            f"[{time_color}]{progress_bar}[/{time_color}]"
        )

        return Panel(
            time_text,
            title=Text("Workflow Time", style="dashboard.title"),
            title_align="left",
            border_style="dashboard.border",
        )
