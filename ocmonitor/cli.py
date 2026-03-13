"""Command line interface for OpenCode Monitor."""

import errno
import json
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console

from . import __version__
from .config import config_manager
from .services.export_service import ExportService
from .services.live_monitor import LiveMonitor
from .services.report_generator import ReportGenerator
from .services.session_analyzer import SessionAnalyzer
from .ui.theme import get_theme
from .utils.error_handling import (
    ErrorHandler,
    create_user_friendly_error,
    handle_errors,
)


def json_serializer(obj):
    """Custom JSON serializer for special types."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif hasattr(obj, "isoformat"):
        return obj.isoformat()
    else:
        return str(obj)


@contextmanager
def cli_error_context(ctx: click.Context, operation_name: str):
    """Context manager for consistent CLI error handling across all commands.
    
    Usage:
        with cli_error_context(ctx, "analyzing sessions"):
            result = perform_operation()
    
    Args:
        ctx: Click context object containing verbose flag
        operation_name: Human-readable description of the operation (for error messages)
    """
    try:
        yield
    except click.exceptions.Exit:
        raise
    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error {operation_name}: {error_msg}", err=True)
        if ctx.obj.get("verbose"):
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


def handle_output_format(result: Any, output_format: str) -> None:
    """Handle output formatting for CLI results.
    
    Centralizes JSON/CSV/table output logic used across multiple commands.
    
    Args:
        result: The result data to output
        output_format: One of 'json', 'csv', or 'table'
    """
    if output_format == "json":
        click.echo(json.dumps(result, indent=2, default=json_serializer))
    elif output_format == "csv":
        click.echo(
            "CSV data would be exported to file. Use 'export' command for file output."
        )


def resolve_path(path: Optional[str], default_to_messages_dir: bool = True) -> str:
    """Resolve path with appropriate default fallback.
    
    Args:
        path: User-provided path or None
        default_to_messages_dir: If True, default to messages_dir; otherwise use cwd
        
    Returns:
        Resolved path string
    """
    if path:
        return path
    
    cfg = config_manager.config
    if default_to_messages_dir:
        return cfg.paths.messages_dir
    
    return str(Path.cwd())


# Sentinel for path placeholder in report method map
_PATH_PLACEHOLDER = object()

# Module-level constant mapping report types to generator methods and parameters
_REPORT_METHOD_MAP = {
    "session": {
        "method": "generate_single_session_report",
        "params": {"path": _PATH_PLACEHOLDER, "output_format": "json"},
    },
    "sessions": {
        "method": "generate_sessions_summary_report",
        "params": {"base_path": _PATH_PLACEHOLDER, "limit": None, "output_format": "table"},
    },
    "daily": {
        "method": "generate_daily_report",
        "params": {"base_path": _PATH_PLACEHOLDER, "month": None, "output_format": "table"},
    },
    "weekly": {
        "method": "generate_weekly_report",
        "params": {
            "base_path": _PATH_PLACEHOLDER,
            "year": None,
            "output_format": "table",
            "breakdown": False,
            "week_start_day": 0,
        },
    },
    "monthly": {
        "method": "generate_monthly_report",
        "params": {"base_path": _PATH_PLACEHOLDER, "year": None, "output_format": "table"},
    },
    "models": {
        "method": "generate_models_report",
        "params": {
            "base_path": _PATH_PLACEHOLDER,
            "timeframe": "all",
            "start_date": None,
            "end_date": None,
            "output_format": "table",
        },
    },
    "projects": {
        "method": "generate_projects_report",
        "params": {
            "base_path": _PATH_PLACEHOLDER,
            "timeframe": "all",
            "start_date": None,
            "end_date": None,
            "output_format": "table",
        },
    },
}


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Path to configuration file"
)
@click.option(
    "--theme", "-t", type=click.Choice(["dark", "light"]), help="Set UI theme (overrides config)"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--no-remote", is_flag=True, help="Disable remote pricing fallback (local-only mode)"
)
@click.option(
    "--color",
    type=click.Choice(["always", "auto", "never"]),
    default="auto",
    help="Force color output: always, auto (default), or never",
)
@click.pass_context
def cli( ctx: click.Context, config: Optional[str], theme: Optional[str], verbose: bool, no_remote: bool, color: str):
    """OpenCode Monitor - Analytics and monitoring for OpenCode sessions.

    Monitor token usage, costs, and performance metrics from your OpenCode
    AI coding sessions with beautiful tables and real-time dashboards.
    """
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["error_handler"] = ErrorHandler(verbose=verbose)

    # Load configuration
    try:
        if config:
            config_manager.config_path = config
            config_manager.reload()

        cfg = config_manager.config
        
        # Override theme if provided via CLI
        if theme:
            cfg.ui.theme = theme
        
        # Store no_remote flag in context for later use
        ctx.obj["no_remote"] = no_remote
            
        ctx.obj["config"] = cfg
        ctx.obj["pricing_data"] = config_manager.load_pricing_data(no_remote=no_remote)

        # Initialize Console with the configured theme
        theme_name = cfg.ui.theme
        theme_obj = get_theme(theme_name)
        console = Console(theme=theme_obj)

        # Apply --color setting
        if color == "always":
            console._color_system = "true"
        elif color == "never":
            console._color_system = None
        # "auto" keeps the default TTY detection

        ctx.obj["console"] = console

        # Initialize services
        analyzer = SessionAnalyzer(ctx.obj["pricing_data"])
        ctx.obj["analyzer"] = analyzer
        ctx.obj["report_generator"] = ReportGenerator(analyzer, console)
        ctx.obj["export_service"] = ExportService(cfg.paths.export_dir)
        ctx.obj["live_monitor"] = LiveMonitor(
            ctx.obj["pricing_data"], console, paths_config=cfg.paths
        )

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error initializing OpenCode Monitor: {error_msg}", err=True)
        if verbose:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


@cli.command()
@click.argument("path", type=click.Path(exists=True), required=False)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
@click.pass_context
def session(ctx: click.Context, path: Optional[str], output_format: str):
    """Analyze a single OpenCode session directory.

    PATH: Path to session directory (defaults to current directory)
    """
    path = resolve_path(path, default_to_messages_dir=False)

    with cli_error_context(ctx, "analyzing session"):
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_single_session_report(path, output_format)

        if result is None:
            click.echo(
                "No valid session data found in the specified directory.", err=True
            )
            ctx.exit(1)

        handle_output_format(result, output_format)


@cli.command()
@click.argument("path", type=click.Path(exists=True), required=False)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
@click.option(
    "--limit", "-l", type=int, default=None, help="Limit number of sessions to analyze"
)
@click.option(
    "--no-group", is_flag=True, help="Show sessions without workflow grouping"
)
@click.option(
    "--source", "-s",
    type=click.Choice(["auto", "sqlite", "files"]),
    default="auto",
    help="Data source: auto (prefer SQLite), sqlite (v1.2.0+), or files (legacy)",
)
@click.option(
    "--days", "-d", type=int, default=None, help="Filter sessions from the last N days"
)
@click.pass_context
def sessions(
    ctx: click.Context,
    path: Optional[str],
    output_format: str,
    limit: Optional[int],
    no_group: bool,
    source: str,
    days: Optional[int],
):
    """Analyze all OpenCode sessions.

    Supports OpenCode v1.2.0+ SQLite database with hierarchical sub-agent view,
    or legacy file-based storage.

    PATH: Path to directory containing session folders (legacy, optional)
          For v1.2.0+, data is read from SQLite database automatically
    """
    config = ctx.obj["config"]
    console = ctx.obj["console"]

    with cli_error_context(ctx, "analyzing sessions"):
        analyzer = ctx.obj["analyzer"]
        report_generator = ctx.obj["report_generator"]

        # Get data source info
        source_info = analyzer.get_data_source_info()
        console.print(f"[status.info]Using data source: {source_info['last_used'] or 'auto-detect'}[/status.info]")

        # Load all sessions first (without limit)
        sessions_list = analyzer.analyze_all_sessions(path)
        console.print(
            f"[status.info]Analyzing {len(sessions_list)} sessions...[/status.info]"
        )

        if not sessions_list:
            console.print("[status.error]No sessions found in the specified directory.[/status.error]")
            ctx.exit(1)

        # Apply date filtering if --days is specified
        if days is not None:
            end_date = date.today()
            start_date = end_date - timedelta(days=days - 1)
            sessions_list = analyzer.filter_sessions_by_date(
                sessions_list, start_date, end_date
            )
            console.print(
                f"[status.info]Filtering to {len(sessions_list)} sessions from the last {days} day(s)...[/status.info]"
            )

        # Apply limit after date filtering
        if limit is not None:
            sessions_list = sessions_list[:limit]
            console.print(
                f"[status.info]Limited to {len(sessions_list)} most recent sessions[/status.info]"
            )

        # Generate summary and display report using filtered sessions
        summary = analyzer.get_sessions_summary(sessions_list)
        result = {
            "type": "sessions_summary",
            "sessions": sessions_list,
            "summary": summary,
        }

        if output_format == "table":
            if not no_group:
                report_generator._display_workflow_sessions_table(
                    sessions_list, summary
                )
            else:
                report_generator._display_sessions_summary_table(sessions_list, summary)
        elif output_format == "json":
            result = report_generator._format_sessions_summary_json(
                sessions_list, summary
            )
        elif output_format == "csv":
            result = report_generator._format_sessions_summary_csv(sessions_list)

        handle_output_format(result, output_format)


def _determine_monitoring_source(source: str, validation: dict) -> tuple[bool, bool]:
    """Determine which monitoring source to use based on validation and user preference.
    
    Args:
        source: User-specified source preference ("auto", "sqlite", or "files")
        validation: Validation result dict containing availability info
        
    Returns:
        Tuple of (use_sqlite, use_files) booleans
    """
    sqlite_available = validation["info"]["sqlite"]["available"]
    files_available = validation["info"]["files"].get("available", False)
    
    use_sqlite = (source == "sqlite") or (source == "auto" and sqlite_available)
    use_files = (source == "files") or (source == "auto" and not sqlite_available and files_available)
    
    return use_sqlite, use_files


def _prompt_workflow_selection(
    live_monitor: LiveMonitor,
    use_sqlite: bool,
    use_files: bool,
    sqlite_available: bool,
    files_available: bool,
    path: Optional[str],
    session_id: Optional[str],
    pick: bool,
    console,
    config,
) -> tuple[Optional[str], str]:
    """Prompt user to select a workflow for monitoring.
    
    Args:
        live_monitor: LiveMonitor instance
        use_sqlite: Whether to use SQLite mode
        use_files: Whether to use file-based mode
        sqlite_available: Whether SQLite is available
        files_available: Whether file-based storage is available
        path: Path to session folders (for file mode)
        session_id: Pre-selected session ID (if any)
        pick: Whether to prompt for workflow selection
        console: Rich console instance
        config: Configuration instance
        
    Returns:
        Tuple of (selected_session_id, mode) where mode is "sqlite", "files",
        "cancelled" (user dismissed picker), or "" (no data source available).
        selected_session_id may be None for auto-detect mode (no --pick, no --session-id).
    """
    selected_session_id = session_id

    if use_sqlite and sqlite_available:
        if pick and not selected_session_id:
            selected_session_id = live_monitor.pick_sqlite_workflow()
            if not selected_session_id:
                console.print("[status.warning]No workflow selected. Exiting.[/status.warning]")
                return None, "cancelled"
        return selected_session_id, "sqlite"

    elif use_files and files_available:
        if not path:
            path = config.paths.messages_dir
        if pick and not selected_session_id:
            assert path is not None
            selected_session_id = live_monitor.pick_file_workflow(path)
            if not selected_session_id:
                console.print("[status.warning]No workflow selected. Exiting.[/status.warning]")
                return None, "cancelled"
        return selected_session_id, "files"

    return None, ""


def _display_validation_results(console, validation: dict, ctx) -> bool:
    """Display validation results and exit if critical errors found.
    
    Args:
        console: Rich console instance
        validation: Validation result dict
        ctx: Click context for exiting
        
    Returns:
        True if validation passed, False if ctx.exit was called
    """
    if not validation["valid"]:
        for issue in validation["issues"]:
            console.print(f"[status.error]Error: {issue}[/status.error]")
        ctx.exit(1)
        return False
    
    if validation["warnings"]:
        for warning in validation["warnings"]:
            console.print(f"[status.warning]Warning: {warning}[/status.warning]")
    
    return True


@cli.command()
@click.argument("path", type=click.Path(exists=True), required=False)
@click.option(
    "--interval", "-i", type=int, default=None, help="Update interval in seconds"
)
@click.option(
    "--pick",
    is_flag=True,
    help="Interactively choose a session/workflow before starting (also enables live switching)",
)
@click.option(
    "--session-id",
    type=str,
    help="Track a specific session/workflow ID (main or sub-agent)",
)
@click.option(
    "--interactive-switch",
    is_flag=True,
    help="Enable in-dashboard workflow switching controls (experimental)",
)
@click.option(
    "--source", "-s",
    type=click.Choice(["auto", "sqlite", "files"]),
    default="auto",
    help="Data source: auto (prefer SQLite), sqlite (v1.2.0+), or files (legacy)"
)
@click.pass_context
def live(
    ctx: click.Context,
    path: Optional[str],
    interval: Optional[int],
    pick: bool,
    session_id: Optional[str],
    interactive_switch: bool,
    source: str,
):
    """Start live dashboard for monitoring the current workflow.

    Monitors the most recent session and its sub-agents (if any) with real-time updates.
    Automatically uses SQLite for OpenCode v1.2.0+ or falls back to file-based storage.

    PATH: Path to directory containing session folders (legacy, optional)
          For v1.2.0+, data is read from SQLite database automatically
    """
    config = ctx.obj["config"]
    console = ctx.obj["console"]

    if interval is None:
        interval = config.ui.live_refresh_interval

    try:
        live_monitor = ctx.obj["live_monitor"]
        interactive_switch = interactive_switch or pick

        # Validate monitoring setup
        validation = live_monitor.validate_monitoring_setup(path if path else None)
        if not _display_validation_results(console, validation, ctx):
            return

        sqlite_available = validation["info"]["sqlite"]["available"]
        files_available = validation["info"]["files"].get("available", False)
        
        # Determine which monitoring method to use
        use_sqlite, use_files = _determine_monitoring_source(source, validation)
        
        # Prompt for workflow selection
        selected_session_id, mode = _prompt_workflow_selection(
            live_monitor,
            use_sqlite,
            use_files,
            sqlite_available,
            files_available,
            path,
            session_id,
            pick,
            console,
            config,
        )
        
        if mode == "":
            console.print("[status.error]No data source available. Please check OpenCode installation.[/status.error]")
            ctx.exit(1)
            return

        if mode == "cancelled":
            return

        # Start monitoring based on selected mode
        if mode == "sqlite":
            live_monitor.start_sqlite_workflow_monitoring(
                interval,
                selected_session_id=selected_session_id,
                interactive_switch=interactive_switch,
            )
        elif mode == "files":
            if not path:
                path = config.paths.messages_dir
            console.print("[status.success]Starting workflow live dashboard (legacy file mode)[/status.success]")
            console.print(f"[status.info]Monitoring: {path}[/status.info]")
            console.print(f"[status.info]Update interval: {interval}s[/status.info]")
            live_monitor.start_monitoring(
                path,
                interval,
                selected_session_id=selected_session_id,
                interactive_switch=interactive_switch,
            )

    except KeyboardInterrupt:
        console.print("\n[status.warning]Live monitoring stopped.[/status.warning]")
    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error in live monitoring: {error_msg}", err=True)
        if ctx.obj["verbose"]:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


@cli.command()
@click.argument("path", type=click.Path(exists=True), required=False)
@click.option("--month", type=str, help="Month to analyze (YYYY-MM format)")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
@click.option("--breakdown", is_flag=True, help="Show per-model breakdown")
@click.pass_context
def daily(
    ctx: click.Context,
    path: Optional[str],
    month: Optional[str],
    output_format: str,
    breakdown: bool,
):
    """Show daily breakdown of OpenCode usage.

    PATH: Path to directory containing session folders
          (defaults to configured messages directory)
    """
    path = resolve_path(path, default_to_messages_dir=True)

    with cli_error_context(ctx, "generating daily breakdown"):
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_daily_report(
            path, month, output_format, breakdown
        )

        handle_output_format(result, output_format)


@cli.command()
@click.argument("path", type=click.Path(exists=True), required=False)
@click.option("--year", type=int, help="Year to analyze")
@click.option(
    "--start-day",
    type=click.Choice(
        ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        case_sensitive=False,
    ),
    default="monday",
    help="Day to start the week (default: monday)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
@click.option("--breakdown", is_flag=True, help="Show per-model breakdown")
@click.pass_context
def weekly(
    ctx: click.Context,
    path: Optional[str],
    year: Optional[int],
    start_day: str,
    output_format: str,
    breakdown: bool,
):
    """Show weekly breakdown of OpenCode usage.

    PATH: Path to directory containing session folders
          (defaults to configured messages directory)

    Examples:
        ocmonitor weekly                    # Default (Monday start)
        ocmonitor weekly --start-day sunday # Sunday to Sunday weeks
        ocmonitor weekly --start-day friday # Friday to Friday weeks
    """
    path = resolve_path(path, default_to_messages_dir=True)

    # Convert day name to weekday number
    from .utils.time_utils import WEEKDAY_MAP

    week_start_day = WEEKDAY_MAP[start_day.lower()]

    with cli_error_context(ctx, "generating weekly breakdown"):
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_weekly_report(
            path, year, output_format, breakdown, week_start_day
        )

        handle_output_format(result, output_format)


@cli.command()
@click.argument("path", type=click.Path(exists=True), required=False)
@click.option("--year", type=int, help="Year to analyze")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
@click.option("--breakdown", is_flag=True, help="Show per-model breakdown")
@click.pass_context
def monthly(
    ctx: click.Context,
    path: Optional[str],
    year: Optional[int],
    output_format: str,
    breakdown: bool,
):
    """Show monthly breakdown of OpenCode usage.

    PATH: Path to directory containing session folders
          (defaults to configured messages directory)
    """
    path = resolve_path(path, default_to_messages_dir=True)

    with cli_error_context(ctx, "generating monthly breakdown"):
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_monthly_report(
            path, year, output_format, breakdown
        )

        handle_output_format(result, output_format)


@cli.command()
@click.argument("name")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
@click.pass_context
def model(ctx: click.Context, name: str, output_format: str):
    """Show detailed breakdown for a specific model.

    NAME: Model name or partial name (fuzzy matched)

    Examples:
        ocmonitor model claude-sonnet-4-5
        ocmonitor model sonnet
        ocmonitor model opus -f json
    """
    with cli_error_context(ctx, "generating model detail"):
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_model_detail_report(name, output_format)

        if result:
            handle_output_format(result, output_format)


@cli.command()
@click.argument("path", type=click.Path(exists=True), required=False)
@click.option(
    "--timeframe",
    type=click.Choice(["daily", "weekly", "monthly", "all"]),
    default="all",
    help="Timeframe for analysis",
)
@click.option("--start-date", type=str, help="Start date (YYYY-MM-DD)")
@click.option("--end-date", type=str, help="End date (YYYY-MM-DD)")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
@click.pass_context
def models(
    ctx: click.Context,
    path: Optional[str],
    timeframe: str,
    start_date: Optional[str],
    end_date: Optional[str],
    output_format: str,
):
    """Show model usage breakdown and statistics.

    PATH: Path to directory containing session folders
          (defaults to configured messages directory)
    """
    path = resolve_path(path, default_to_messages_dir=True)

    with cli_error_context(ctx, "generating model breakdown"):
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_models_report(
            path, timeframe, start_date, end_date, output_format
        )

        handle_output_format(result, output_format)


@cli.command()
@click.argument("path", type=click.Path(exists=True), required=False)
@click.option(
    "--timeframe",
    type=click.Choice(["daily", "weekly", "monthly", "all"]),
    default="all",
    help="Timeframe for analysis",
)
@click.option("--start-date", type=str, help="Start date (YYYY-MM-DD)")
@click.option("--end-date", type=str, help="End date (YYYY-MM-DD)")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
@click.pass_context
def projects(
    ctx: click.Context,
    path: Optional[str],
    timeframe: str,
    start_date: Optional[str],
    end_date: Optional[str],
    output_format: str,
):
    """Show project usage breakdown and statistics.

    PATH: Path to directory containing session folders
          (defaults to configured messages directory)
    """
    path = resolve_path(path, default_to_messages_dir=True)

    with cli_error_context(ctx, "generating project breakdown"):
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_projects_report(
            path, timeframe, start_date, end_date, output_format
        )

        handle_output_format(result, output_format)


def _generate_export_report(report_type: str, path: Optional[str], report_generator) -> Optional[dict]:
    """Generate report data for export based on report type.
    
    Args:
        report_type: Type of report to generate
        path: Path to analyze
        report_generator: ReportGenerator instance
        
    Returns:
        Report data dictionary or None if report type is invalid
    """
    if report_type not in _REPORT_METHOD_MAP:
        return None
    
    report_config = _REPORT_METHOD_MAP[report_type]
    method_name = report_config["method"]
    params = report_config["params"].copy()
    
    # Replace path placeholders with actual path value
    for key in params:
        if params[key] is _PATH_PLACEHOLDER:
            params[key] = path
    
    # Get the method from report_generator and call it with unpacked params
    method = getattr(report_generator, method_name)
    return method(**params)


def _display_export_summary(
    console, 
    output_path: str, 
    export_service, 
    report_type: str
) -> None:
    """Display export completion summary.
    
    Args:
        console: Rich console instance
        output_path: Path to the exported file
        export_service: ExportService instance
        report_type: Type of report that was exported
    """
    summary = export_service.get_export_summary(output_path)
    console.print(f"[status.success]✅ Export completed successfully![/status.success]")
    console.print(f"[metric.label]File:[/metric.label] [metric.value]{output_path}[/metric.value]")
    console.print(f"[metric.label]Size:[/metric.label] [metric.value]{summary.get('size_human', 'Unknown')}[/metric.value]")
    if "rows" in summary:
        console.print(f"[metric.label]Rows:[/metric.label] [metric.value]{summary['rows']}[/metric.value]")


@cli.command()
@click.argument(
    "report_type",
    type=click.Choice(
        ["session", "sessions", "daily", "weekly", "monthly", "models", "projects"]
    ),
)
@click.argument("path", type=click.Path(exists=True), required=False)
@click.option(
    "--format",
    "-f",
    "export_format",
    type=click.Choice(["csv", "json"]),
    help="Export format (defaults to configured format)",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--include-raw", is_flag=True, help="Include raw data in export")
@click.pass_context
def export(
    ctx: click.Context,
    report_type: str,
    path: Optional[str],
    export_format: Optional[str],
    output: Optional[str],
    include_raw: bool,
):
    """Export analysis results to file.

    REPORT_TYPE: Type of report to export
    PATH: Path to analyze (defaults to configured messages directory)
    """
    config = ctx.obj["config"]
    console = ctx.obj["console"]

    path = resolve_path(path, default_to_messages_dir=True)

    if not export_format:
        export_format = config.export.default_format

    with cli_error_context(ctx, "exporting data"):
        report_generator = ctx.obj["report_generator"]
        export_service = ctx.obj["export_service"]

        # Generate report data using method mapping
        report_data = _generate_export_report(report_type, path, report_generator)

        if not report_data:
            console.print("[status.error]No data to export.[/status.error]")
            ctx.exit(1)

        # Export the data
        output_path = export_service.export_report_data(
            report_data,
            report_type,
            export_format,
            output,
            config.export.include_metadata,
        )

        # Display export summary
        _display_export_summary(console, output_path, export_service, report_type)


@cli.group()
def config():
    """Configuration management commands."""
    pass


@config.command("show")
@click.pass_context
def config_show(ctx: click.Context):
    """Show current configuration."""
    with cli_error_context(ctx, "showing configuration"):
        config = ctx.obj["config"]
        pricing_data = ctx.obj["pricing_data"]
        console = ctx.obj["console"]

        console.print("[table.title]📋 Current Configuration:[/table.title]")
        console.print()
        console.print("[table.header]📁 Paths:[/table.header]")
        console.print(f"  [metric.label]Database file:[/metric.label] [metric.value]{config.paths.database_file}[/metric.value]")
        console.print(f"  [metric.label]Messages directory:[/metric.label] [metric.value]{config.paths.messages_dir}[/metric.value]")
        console.print(f"  [metric.label]Export directory:[/metric.label] [metric.value]{config.paths.export_dir}[/metric.value]")
        console.print()
        console.print("[table.header]🎨 UI Settings:[/table.header]")
        console.print(f"  [metric.label]Table style:[/metric.label] [metric.value]{config.ui.table_style}[/metric.value]")
        console.print(f"  [metric.label]Theme:[/metric.label] [metric.value]{config.ui.theme}[/metric.value]")
        console.print(f"  [metric.label]Progress bars:[/metric.label] [metric.value]{config.ui.progress_bars}[/metric.value]")
        console.print(f"  [metric.label]Colors:[/metric.label] [metric.value]{config.ui.colors}[/metric.value]")
        console.print(f"  [metric.label]Live refresh interval:[/metric.label] [metric.value]{config.ui.live_refresh_interval}s[/metric.value]")
        console.print()
        console.print("[table.header]📤 Export Settings:[/table.header]")
        console.print(f"  [metric.label]Default format:[/metric.label] [metric.value]{config.export.default_format}[/metric.value]")
        console.print(f"  [metric.label]Include metadata:[/metric.label] [metric.value]{config.export.include_metadata}[/metric.value]")
        console.print()
        console.print("[table.header]🤖 Models:[/table.header]")
        console.print(f"  [metric.label]Configured models:[/metric.label] [metric.value]{len(pricing_data)}[/metric.value]")
        for model_name in sorted(pricing_data.keys()):
            console.print(f"    - [table.row.model]{model_name}[/table.row.model]")


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str):
    """Set configuration value.

    KEY: Configuration key (e.g., 'paths.messages_dir')
    VALUE: New value to set
    """
    click.echo(f"Configuration setting is not yet implemented.")
    click.echo(f"Would set {key} = {value}")
    click.echo("Please edit the config.toml file directly for now.")


@cli.command()
@click.option("--port", "-p", type=int, default=None,
              help="Port to serve metrics on (default: 9090)")
@click.option("--host", type=str, default=None,
              help="Host to bind to (default: 0.0.0.0)")
@click.pass_context
def metrics(ctx, port, host):
    """Start a Prometheus metrics endpoint.

    Exposes session analytics at /metrics for Prometheus scraping.
    """
    config = ctx.obj["config"]
    console = ctx.obj["console"]

    port = port or config.metrics.port
    host = host or config.metrics.host

    try:
        from .services.metrics_server import MetricsServer
    except ImportError:
        click.echo(
            "prometheus_client is required for the metrics command.\n"
            "Install it with: pip install prometheus_client>=0.17.0",
            err=True,
        )
        ctx.exit(1)
        return

    try:
        console.print(f"[status.success]Starting Prometheus metrics server...[/status.success]")
        console.print(f"[metric.label]Endpoint:[/metric.label] [metric.value]http://{host}:{port}/metrics[/metric.value]")
        console.print("[dim]Press Ctrl+C to stop.[/dim]")

        server = MetricsServer(ctx.obj["pricing_data"], host=host, port=port)
        server.start()
    except KeyboardInterrupt:
        console.print("\n[status.warning]Metrics server stopped.[/status.warning]")
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            click.echo(f"Port {port} is already in use. Try a different port with --port.", err=True)
        else:
            click.echo(f"Error starting metrics server: {e}", err=True)
        ctx.exit(1)
    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error starting metrics server: {error_msg}", err=True)
        if ctx.obj["verbose"]:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


@cli.command()
@click.pass_context
def agents(ctx: click.Context):
    """List all detected agents and their types.

    Shows built-in and user-defined agents, indicating which are main agents
    (stay in same session) and which are sub-agents (create separate sessions).
    """
    with cli_error_context(ctx, "listing agents"):
        from .services.agent_registry import AgentRegistry

        registry = AgentRegistry()
        console = ctx.obj["console"]

        console.print("[table.header]Main agents[/table.header] [dim](stay in same session)[/dim]:")
        for agent in sorted(registry.get_all_main_agents()):
            console.print(f"  - [table.row.main]{agent}[/table.row.main]")

        console.print()
        console.print("[table.header]Sub-agents[/table.header] [dim](create separate sessions)[/dim]:")
        for agent in sorted(registry.get_all_sub_agents()):
            console.print(f"  - [table.row.model]{agent}[/table.row.model]")

        console.print()
        console.print(f"[dim]Agent definitions from: {registry.agents_dir}[/dim]")


def main():
    """Entry point for the CLI application."""
    cli()
