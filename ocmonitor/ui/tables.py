"""Rich table formatting for OpenCode Monitor."""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from ..models.session import SessionData, TokenUsage
from ..models.analytics import DailyUsage, ModelUsageStats, ModelDetailStats
from ..models.tool_usage import ToolUsageStats
from ..utils.file_utils import FileProcessor
from ..utils.time_utils import TimeUtils, compute_p50_output_rate
from ..utils.formatting import ColorFormatter


class TableFormatter:
    """Formatter for creating Rich tables."""

    def __init__(self, console: Optional[Console] = None, currency_converter=None):
        """Initialize table formatter.

        Args:
            console: Rich console instance. If None, creates a new one.
            currency_converter: Optional CurrencyConverter for currency formatting.
        """
        self.console = console or Console()
        self.currency_converter = currency_converter

    def format_number(self, number: int) -> str:
        """Format numbers with thousands separators."""
        return f"{number:,}"

    def format_currency(self, amount: Decimal) -> str:
        """Format currency amounts."""
        if self.currency_converter:
            return self.currency_converter.format(amount)
        return f"${amount:.2f}"

    def format_percentage(self, value: float, total: float) -> str:
        """Format percentage values."""
        if total == 0:
            return "0.0%"
        percentage = (value / total) * 100
        return f"{percentage:.1f}%"

    def get_cost_color(self, cost: Decimal, quota: Optional[Decimal] = None) -> str:
        """Get color for cost based on quota using semantic theme tags."""
        return ColorFormatter.get_cost_color(cost, quota, default_style="table.row.main")

    @staticmethod
    def _compact_models_display(models: list, max_groups: int = 3) -> str:
        """Format a list of provider/model strings compactly.

        Groups models by provider:
          - single model  → provider/model
          - multi models  → provider/{model1, model2}
          - bare model    → model
        Truncates to max_groups provider-groups with '(+N more)'.
        """
        provider_models: dict = {}
        bare: list = []
        for display_model in models:
            if '/' in display_model:
                prov, _, mod = display_model.partition('/')
                provider_models.setdefault(prov, [])
                if mod not in provider_models[prov]:
                    provider_models[prov].append(mod)
            else:
                if display_model not in bare:
                    bare.append(display_model)

        parts: list = []
        for prov in sorted(provider_models.keys()):
            mods = sorted(provider_models[prov])
            if len(mods) == 1:
                parts.append(f"{prov}/{mods[0]}")
            else:
                parts.append(f"{prov}/{{{', '.join(mods)}}}")
        parts.extend(sorted(bare))

        if len(parts) <= max_groups:
            return ", ".join(parts)
        return ", ".join(parts[:max_groups]) + f" (+{len(parts) - max_groups} more)"

    def create_sessions_table(self, sessions: List[SessionData], pricing_data: Dict[str, Any],
                         force_recalculate: bool = False) -> Table:
        """Create a table for multiple sessions using semantic theme styles."""
        table = Table(
            title="OpenCode Sessions Summary",
            show_header=True,
            header_style="table.header",
            title_style="table.title"
        )

        # Add columns
        table.add_column("Started", style="table.row.time", no_wrap=True)
        table.add_column("Duration", style="table.row.time", no_wrap=True)
        table.add_column("Session", style="table.row.main", max_width=35)
        table.add_column("Provider", style="table.row.model", max_width=20)
        table.add_column("Model", style="table.row.model", max_width=30)
        table.add_column("Interactions", justify="right", style="status.success")
        table.add_column("Input Tokens", justify="right", style="table.row.tokens")
        table.add_column("Output Tokens", justify="right", style="table.row.tokens")
        table.add_column("Total Tokens", justify="right", style="table.row.tokens")
        table.add_column("Cost", justify="right", style="table.row.cost")
        table.add_column("Speed", justify="right", style="table.row.time")

        # Sort sessions by start time
        sorted_sessions = sorted(sessions, key=lambda s: s.start_time or s.session_id)

        total_interactions = 0
        total_tokens = TokenUsage()
        total_cost = Decimal('0.0')
        all_interaction_rates: list[float] = []

        for session in sorted_sessions:
            session_cost = session.calculate_total_cost(pricing_data, force_recalculate)
            session_tokens = session.total_tokens

            # Update totals
            total_interactions += session.interaction_count
            total_tokens.input += session_tokens.input
            total_tokens.output += session_tokens.output
            total_tokens.cache_write += session_tokens.cache_write
            total_tokens.cache_read += session_tokens.cache_read
            total_cost += session_cost

            # Get model breakdown for session
            model_breakdown = session.get_model_breakdown(pricing_data, force_recalculate)

            # Add rows for each model
            for i, (display_model, stats) in enumerate(model_breakdown.items()):
                # Show session info only for first model
                if i == 0:
                    start_time = session.start_time.strftime('%Y-%m-%d %H:%M:%S') if session.start_time else 'N/A'
                    duration = self._format_duration(session.duration_ms) if session.duration_ms else 'N/A'
                    session_display = session.display_title
                    # Truncate if too long for display
                    if len(session_display) > 35:
                        session_display = session_display[:32] + "..."
                else:
                    start_time = ""
                    duration = ""
                    session_display = ""

                # Format model name
                provider, model = FileProcessor.split_provider_model(display_model)
                provider_text = Text(provider[:17] + "..." if len(provider) > 20 else provider)
                model_text = Text(model[:27] + "..." if len(model) > 30 else model)

                # Get cost color
                cost_color = self.get_cost_color(stats['cost'])

                # Calculate speed (p50 output tokens per second)
                rates = stats.get('interaction_rates', [])
                all_interaction_rates.extend(rates)
                if rates:
                    import statistics
                    speed = statistics.median(rates)
                    speed_text = f"{speed:.1f} t/s"
                else:
                    speed_text = "-"

                table.add_row(
                    start_time,
                    duration,
                    session_display,
                    provider_text,
                    model_text,
                    self.format_number(stats['files']),
                    self.format_number(stats['tokens'].input),
                    self.format_number(stats['tokens'].output),
                    self.format_number(stats['tokens'].total),
                    Text(self.format_currency(stats['cost']), style=cost_color),
                    speed_text
                )

        # Add separator and totals
        table.add_section()
        # Calculate p50 speed for totals
        if all_interaction_rates:
            import statistics
            total_speed = statistics.median(all_interaction_rates)
            total_speed_text = f"{total_speed:.1f} t/s"
        else:
            total_speed_text = "-"

        table.add_row(
            Text("TOTALS", style="table.footer"),
            "",
            "",  # Empty session column
            "",  # Empty provider column
            Text(f"{len(sorted_sessions)} sessions", style="table.footer"),
            Text(self.format_number(total_interactions), style="status.success"),
            Text(self.format_number(total_tokens.input), style="table.row.tokens"),
            Text(self.format_number(total_tokens.output), style="table.row.tokens"),
            Text(self.format_number(total_tokens.total), style="table.row.tokens"),
            Text(self.format_currency(total_cost), style="table.row.cost"),
            Text(total_speed_text, style="table.row.time")
        )

        return table

    def create_session_table(self, session: SessionData, pricing_data: Dict[str, Any],
                        force_recalculate: bool = False) -> Table:
        """Create a table for a single session using semantic theme styles."""
        table = Table(
            title=f"Session: {session.display_title}",
            show_header=True,
            header_style="table.header",
            title_style="table.title"
        )

        # Add columns
        table.add_column("File", style="table.row.time", max_width=30)
        table.add_column("Provider", style="table.row.model", max_width=20)
        table.add_column("Model", style="table.row.model", max_width=30)
        table.add_column("Input", justify="right", style="table.row.tokens")
        table.add_column("Output", justify="right", style="table.row.tokens")
        table.add_column("Cache W", justify="right", style="status.success")
        table.add_column("Cache R", justify="right", style="status.success")
        table.add_column("Total", justify="right", style="table.row.tokens")
        table.add_column("Cost", justify="right", style="table.row.cost")
        table.add_column("Duration", justify="right", style="table.row.time")

        total_cost = Decimal('0.0')
        total_tokens = TokenUsage()

        for file in session.files:
            cost = file.calculate_cost(pricing_data, force_recalculate)
            total_cost += cost
            total_tokens.input += file.tokens.input
            total_tokens.output += file.tokens.output
            total_tokens.cache_write += file.tokens.cache_write
            total_tokens.cache_read += file.tokens.cache_read

            duration = ""
            if file.time_data and file.time_data.duration_ms:
                duration = self._format_duration(file.time_data.duration_ms)

            cost_color = self.get_cost_color(cost)

            provider, model = FileProcessor.split_provider_model(file.display_model)

            table.add_row(
                Text(file.file_name[:27] + "..." if len(file.file_name) > 30 else file.file_name),
                Text(provider[:17] + "..." if len(provider) > 20 else provider),
                Text(model[:27] + "..." if len(model) > 30 else model),
                self.format_number(file.tokens.input),
                self.format_number(file.tokens.output),
                self.format_number(file.tokens.cache_write),
                self.format_number(file.tokens.cache_read),
                self.format_number(file.tokens.total),
                Text(self.format_currency(cost), style=cost_color),
                duration
            )

        # Add totals
        table.add_section()
        table.add_row(
            Text("TOTALS", style="table.footer"),
            "",
            "",
            Text(self.format_number(total_tokens.input), style="table.row.tokens"),
            Text(self.format_number(total_tokens.output), style="table.row.tokens"),
            Text(self.format_number(total_tokens.cache_write), style="status.success"),
            Text(self.format_number(total_tokens.cache_read), style="status.success"),
            Text(self.format_number(total_tokens.total), style="table.row.tokens"),
            Text(self.format_currency(total_cost), style="table.row.cost"),
            ""
        )

        return table

    def create_daily_table(self, daily_usage: List[DailyUsage], pricing_data: Dict[str, Any],
                      force_recalculate: bool = False) -> Table:
        """Create a table for daily usage breakdown using semantic theme styles."""
        table = Table(
            title="Daily Usage Breakdown",
            show_header=True,
            header_style="table.header",
            title_style="table.title"
        )

        # Add columns
        table.add_column("Date", style="table.row.time", no_wrap=True)
        table.add_column("Sessions", justify="right", style="status.success")
        table.add_column("Interactions", justify="right", style="status.success")
        table.add_column("Input Tokens", justify="right", style="table.row.tokens")
        table.add_column("Output Tokens", justify="right", style="table.row.tokens")
        table.add_column("Total Tokens", justify="right", style="table.row.tokens")
        table.add_column("Cost", justify="right", style="table.row.cost")
        table.add_column("Models", style="table.row.model")

        total_sessions = 0
        total_interactions = 0
        total_tokens = TokenUsage()
        total_cost = Decimal('0.0')

        for day in daily_usage:
            day_cost = day.calculate_total_cost(pricing_data, force_recalculate)
            day_tokens = day.total_tokens

            total_sessions += len(day.sessions)
            total_interactions += day.total_interactions
            total_tokens.input += day_tokens.input
            total_tokens.output += day_tokens.output
            total_tokens.cache_write += day_tokens.cache_write
            total_tokens.cache_read += day_tokens.cache_read
            total_cost += day_cost

            models_text = self._compact_models_display(day.models_used)

            cost_color = self.get_cost_color(day_cost)

            table.add_row(
                day.date.strftime('%Y-%m-%d'),
                self.format_number(len(day.sessions)),
                self.format_number(day.total_interactions),
                self.format_number(day_tokens.input),
                self.format_number(day_tokens.output),
                self.format_number(day_tokens.total),
                Text(self.format_currency(day_cost), style=cost_color),
                Text(models_text, style="table.row.model")
            )

        # Add totals
        table.add_section()
        table.add_row(
            Text("TOTALS", style="table.footer"),
            Text(self.format_number(total_sessions), style="status.success"),
            Text(self.format_number(total_interactions), style="status.success"),
            Text(self.format_number(total_tokens.input), style="table.row.tokens"),
            Text(self.format_number(total_tokens.output), style="table.row.tokens"),
            Text(self.format_number(total_tokens.total), style="table.row.tokens"),
            Text(self.format_currency(total_cost), style="table.row.cost"),
            ""
        )

        return table

    def create_model_breakdown_table(self, model_stats: List[ModelUsageStats]) -> Table:
        """Create a table for model usage breakdown using semantic theme styles."""
        table = Table(
            title="Model Usage Breakdown",
            show_header=True,
            header_style="table.header",
            title_style="table.title"
        )

        # Add columns
        table.add_column("Provider", style="table.row.model", max_width=20)
        table.add_column("Model", style="table.row.model", max_width=30)
        table.add_column("Sessions", justify="right", style="status.success")
        table.add_column("Interactions", justify="right", style="status.success")
        table.add_column("Input Tokens", justify="right", style="table.row.tokens")
        table.add_column("Output Tokens", justify="right", style="table.row.tokens")
        table.add_column("Cache Write", justify="right", style="table.row.tokens")
        table.add_column("Cache Read", justify="right", style="table.row.tokens")
        table.add_column("Total Tokens", justify="right", style="table.row.tokens")
        table.add_column("Cost", justify="right", style="table.row.cost")
        table.add_column("Cost %", justify="right", style="table.row.cost")
        table.add_column("Speed", justify="right", style="table.row.time")

        total_cost = sum(stat.total_cost for stat in model_stats)

        for stat in model_stats:
            cost_percentage = self.format_percentage(float(stat.total_cost), float(total_cost))
            cost_color = self.get_cost_color(stat.total_cost)

            # Format speed
            speed = stat.p50_output_rate
            if speed == 0:
                speed_text = "-"
            else:
                speed_text = f"{speed:.1f} t/s"

            provider, model = FileProcessor.split_provider_model(stat.display_model)

            table.add_row(
                Text(provider[:17] + "..." if len(provider) > 20 else provider),
                Text(model[:27] + "..." if len(model) > 30 else model),
                self.format_number(stat.total_sessions),
                self.format_number(stat.total_interactions),
                self.format_number(stat.total_tokens.input),
                self.format_number(stat.total_tokens.output),
                self.format_number(stat.total_tokens.cache_write),
                self.format_number(stat.total_tokens.cache_read),
                self.format_number(stat.total_tokens.total),
                Text(self.format_currency(stat.total_cost), style=cost_color),
                Text(cost_percentage, style=cost_color),
                speed_text
            )

        return table

    def create_progress_bar(self, percentage: float, width: int = 20) -> str:
        """Create a text-based progress bar."""
        filled = int(width * max(0.0, min(100.0, percentage)) / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}] {percentage:.1f}%"

    def _format_duration(self, milliseconds: int) -> str:
        """Format duration in milliseconds to hours and minutes format."""
        return TimeUtils.format_duration_hm(milliseconds)

    def create_summary_panel(self, sessions: List[SessionData], pricing_data: Dict[str, Any],
                        force_recalculate: bool = False) -> Panel:
        """Create a summary panel with key metrics using semantic theme styles."""
        if not sessions:
            return Panel("No sessions found", title="Summary", title_align="left")

        total_sessions = len(sessions)
        total_interactions = sum(session.interaction_count for session in sessions)
        total_tokens = TokenUsage()
        total_cost = Decimal('0.0')
        models_used = set()

        for session in sessions:
            session_tokens = session.total_tokens
            total_tokens.input += session_tokens.input
            total_tokens.output += session_tokens.output
            total_tokens.cache_write += session_tokens.cache_write
            total_tokens.cache_read += session_tokens.cache_read
            total_cost += session.calculate_total_cost(pricing_data, force_recalculate)
            models_used.update(session.models_used)

        # Create summary text using semantic tags
        summary_lines = [
            f"[metric.important]Sessions:[/metric.important] [metric.value]{self.format_number(total_sessions)}[/metric.value]",
            f"[metric.important]Interactions:[/metric.important] [metric.value]{self.format_number(total_interactions)}[/metric.value]",
            f"[metric.important]Total Tokens:[/metric.important] [metric.tokens]{self.format_number(total_tokens.total)}[/metric.tokens]",
            f"[metric.important]Total Cost:[/metric.important] [metric.cost]{self.format_currency(total_cost)}[/metric.cost]",
            f"[metric.important]Models Used:[/metric.important] [metric.value]{len(models_used)}[/metric.value]"
        ]

        return Panel(
            "\n".join(summary_lines),
            title="Summary",
            title_align="left",
            border_style="table.header"
        )

    def create_hierarchical_table(self, hierarchy: Dict[str, Any], pricing_data: Dict[str, Any]) -> Table:
        """Create a hierarchical table showing parent sessions with sub-agents.
        
        Args:
            hierarchy: Dictionary with 'root_sessions' and 'source'
            pricing_data: Model pricing information
            
        Returns:
            Rich Table with hierarchical display
        """
        source = hierarchy.get('source', 'unknown')
        root_sessions = hierarchy.get('root_sessions', [])
        
        table = Table(
            title=f"OpenCode Sessions (Source: {source.upper()})",
            show_header=True,
            header_style="table.header",
            title_style="table.title"
        )
        
        # Add columns
        table.add_column("Session", style="table.row.main", max_width=40)
        table.add_column("Type", style="table.row.model", width=12)
        table.add_column("Interactions", justify="right", style="status.success")
        table.add_column("Tokens", justify="right", style="table.row.tokens")
        table.add_column("Cost", justify="right", style="table.row.cost")
        table.add_column("Duration", justify="right", style="table.row.time")
        
        for root in root_sessions:
            session = root['session']
            sub_agents = root.get('sub_agents', [])
            
            # Parent session row
            session_cost = session.calculate_total_cost(pricing_data)
            duration = self._format_duration(session.duration_ms) if session.duration_ms else 'N/A'
            title = session.display_title
            if len(title) > 37:
                title = title[:34] + "..."
            
            # Format parent row with folder icon
            parent_text = f"📁 {title}"
            
            table.add_row(
                Text(parent_text, style="bold"),
                "Parent",
                self.format_number(session.interaction_count),
                self.format_number(session.total_tokens.total),
                Text(self.format_currency(session_cost), style=self.get_cost_color(session_cost)),
                duration
            )
            
            # Sub-agent rows
            for sub in sub_agents:
                sub_cost = sub.calculate_total_cost(pricing_data)
                sub_duration = self._format_duration(sub.duration_ms) if sub.duration_ms else 'N/A'
                sub_title = sub.display_title
                if len(sub_title) > 35:
                    sub_title = sub_title[:32] + "..."
                
                # Indent sub-agent with tree branch
                sub_text = f"└── ↳ {sub_title}"
                
                table.add_row(
                    Text(sub_text, style="dim"),
                    "Sub-agent",
                    self.format_number(sub.interaction_count),
                    self.format_number(sub.total_tokens.total),
                    Text(self.format_currency(sub_cost), style=self.get_cost_color(sub_cost)),
                    sub_duration
                )
            
            # Add separator after each parent group (except last)
            if root != root_sessions[-1]:
                table.add_section()
        
        return table

    def create_live_dashboard_table(self, hierarchy: Dict[str, Any], pricing_data: Dict[str, Any]) -> Table:
        """Create a live dashboard table with hierarchical display.
        
        Args:
            hierarchy: Dictionary with 'root_sessions' and 'source'
            pricing_data: Model pricing information
            
        Returns:
            Rich Table formatted for live dashboard
        """
        source = hierarchy.get('source', 'unknown')
        root_sessions = hierarchy.get('root_sessions', [])
        
        # Get top 10 most recent parent sessions
        recent_roots = root_sessions[:10]
        
        table = Table(
            show_header=True,
            header_style="table.header",
            title_style="table.title",
            expand=True
        )
        
        # Add columns
        table.add_column("Session", style="table.row.main", max_width=45)
        table.add_column("Tokens", justify="right", style="table.row.tokens", width=12)
        table.add_column("Cost", justify="right", style="table.row.cost", width=10)
        table.add_column("Quota", justify="left", style="table.row.time", width=20)
        
        for root in recent_roots:
            session = root['session']
            sub_agents = root.get('sub_agents') or []
            sub_costs = [sub.calculate_total_cost(pricing_data) for sub in sub_agents]
            
            session_total_tokens = session.total_tokens.total + sum(
                sub.total_tokens.total for sub in sub_agents
            )
            
            # Parent session
            session_cost = session.calculate_total_cost(pricing_data)
            session_total_cost = session_cost + sum(sub_costs)
            title = session.display_title
            if len(title) > 40:
                title = title[:37] + "..."
            
            # Progress bar for quota
            quota_bar = self.create_progress_bar(session.duration_percentage, width=12)
            
            parent_text = f"📁 {title}"
            
            table.add_row(
                Text(parent_text, style="bold"),
                self.format_number(session_total_tokens),
                Text(self.format_currency(session_total_cost), style=self.get_cost_color(session_total_cost)),
                quota_bar
            )
            
            # Sub-agents (show max 3)
            for i, sub in enumerate(sub_agents[:3]):
                sub_cost = sub_costs[i]
                sub_title = sub.display_title
                if len(sub_title) > 38:
                    sub_title = sub_title[:35] + "..."
                
                sub_text = f"└── ↳ {sub_title}"
                
                table.add_row(
                    Text(sub_text, style="dim"),
                    self.format_number(sub.total_tokens.total),
                    Text(self.format_currency(sub_cost), style=self.get_cost_color(sub_cost)),
                    ""
                )
            
            # Show indicator if more sub-agents exist
            if len(sub_agents) > 3:
                table.add_row(
                    Text(f"    ... and {len(sub_agents) - 3} more sub-agents", style="dim italic"),
                    "", "", ""
                )
            
            # Add separator
            if root != recent_roots[-1]:
                table.add_section()

        return table

    def create_model_detail_panel(self, stats: ModelDetailStats) -> Panel:
        """Create a key-value panel for model detail stats.

        Args:
            stats: ModelDetailStats with all model metrics

        Returns:
            Rich Panel with formatted model details
        """
        lines = []

        # Date info
        first_used = stats.first_used.strftime('%Y-%m-%d') if stats.first_used else 'N/A'
        last_used = stats.last_used.strftime('%Y-%m-%d') if stats.last_used else 'N/A'
        lines.append(f"[metric.label]First Used[/metric.label]      [metric.value]{first_used}[/metric.value]")
        lines.append(f"[metric.label]Last Used[/metric.label]       [metric.value]{last_used}[/metric.value]")
        lines.append(f"[metric.label]Sessions[/metric.label]        [metric.value]{self.format_number(stats.total_sessions)}[/metric.value]")
        lines.append(f"[metric.label]Days Used[/metric.label]       [metric.value]{self.format_number(stats.total_days_used)}[/metric.value]")
        lines.append(f"[metric.label]Interactions[/metric.label]    [metric.value]{self.format_number(stats.total_interactions)}[/metric.value]")
        lines.append("")

        # Token breakdown
        lines.append(f"[metric.label]Input Tokens[/metric.label]    [metric.tokens]{self.format_number(stats.total_tokens.input)}[/metric.tokens]")
        lines.append(f"[metric.label]Output Tokens[/metric.label]   [metric.tokens]{self.format_number(stats.total_tokens.output)}[/metric.tokens]")
        lines.append(f"[metric.label]Cache Read[/metric.label]      [metric.tokens]{self.format_number(stats.total_tokens.cache_read)}[/metric.tokens]")
        lines.append(f"[metric.label]Cache Write[/metric.label]     [metric.tokens]{self.format_number(stats.total_tokens.cache_write)}[/metric.tokens]")
        lines.append("")

        # Cost info
        lines.append(f"[metric.label]Total Cost[/metric.label]      [metric.cost]{self.format_currency(stats.total_cost)}[/metric.cost]")
        lines.append(f"[metric.label]Avg/Day[/metric.label]         [metric.cost]{self.format_currency(stats.avg_cost_per_day)}[/metric.cost]")
        lines.append(f"[metric.label]Avg/Session[/metric.label]     [metric.cost]{self.format_currency(stats.avg_cost_per_session)}[/metric.cost]")
        lines.append("")

        # Speed
        speed = stats.p50_output_rate
        speed_text = f"{speed:.1f} tok/s (p50)" if speed > 0 else "N/A"
        lines.append(f"[metric.label]Output Speed[/metric.label]    [metric.value]{speed_text}[/metric.value]")

        return Panel(
            "\n".join(lines),
            title=f"Model Detail: {stats.model_name}",
            title_align="left",
            border_style="table.header",
        )

    def create_model_tool_table(self, tool_stats: list[ToolUsageStats], model_name: str) -> Table:
        """Create a table showing tool usage for a model.

        Args:
            tool_stats: List of ToolUsageStats
            model_name: Model name for title

        Returns:
            Rich Table with tool usage breakdown
        """
        table = Table(
            title=f"Tool Usage for {model_name}",
            show_header=True,
            header_style="table.header",
            title_style="table.title",
        )

        table.add_column("Tool", style="table.row.main")
        table.add_column("Calls", justify="right", style="table.row.tokens")
        table.add_column("Success", justify="right", style="status.success")
        table.add_column("Failed", justify="right", style="status.error")
        table.add_column("Success Rate", justify="right")

        for tool in tool_stats:
            # Color-code the success rate
            rate = tool.success_rate
            if rate >= 90:
                rate_style = "status.success"
            elif rate >= 70:
                rate_style = "status.warning"
            else:
                rate_style = "status.error"

            table.add_row(
                tool.tool_name,
                self.format_number(tool.total_calls),
                self.format_number(tool.success_count),
                self.format_number(tool.failure_count),
                Text(f"{rate:.0f}%", style=rate_style),
            )

        return table
