"""Command line interface for OpenCode Monitor."""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

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


@click.group(invoke_without_command=True)
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
@click.pass_context
def cli(ctx: click.Context, config: Optional[str], theme: Optional[str], verbose: bool, no_remote: bool):
    """OpenCode Monitor - Analytics and monitoring for OpenCode sessions.

    Monitor token usage, costs, and performance metrics from your OpenCode
    AI coding sessions with beautiful tables and real-time dashboards.

    Run without a subcommand to launch the interactive TUI.
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

    # Launch TUI when no subcommand is given
    if ctx.invoked_subcommand is None:
        _launch_tui(ctx)


def _launch_tui(ctx: click.Context) -> None:
    """Launch the interactive TUI if in an interactive terminal."""
    import sys

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        # Non-interactive: show help instead
        click.echo(ctx.get_help())
        return

    try:
        from .tui.app import OCMonitorApp

        app = OCMonitorApp(
            config=ctx.obj["config"],
            pricing_data=ctx.obj["pricing_data"],
            no_remote=ctx.obj.get("no_remote", False),
        )
        app.run()
    except ImportError:
        click.echo(
            "TUI requires the 'textual' package. Install it with:\n"
            "  pip install 'textual>=0.50.0'",
            err=True,
        )
        ctx.exit(1)


@cli.command()
@click.pass_context
def tui(ctx: click.Context):
    """Launch the interactive TUI dashboard."""
    _launch_tui(ctx)


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
    if not path:
        path = str(Path.cwd())

    try:
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_single_session_report(path, output_format)

        if result is None:
            click.echo(
                "No valid session data found in the specified directory.", err=True
            )
            ctx.exit(1)

        if output_format == "json":
            click.echo(json.dumps(result, indent=2, default=json_serializer))
        elif output_format == "csv":
            click.echo(
                "CSV data would be exported to file. Use 'export' command for file output."
            )

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error analyzing session: {error_msg}", err=True)
        if ctx.obj["verbose"]:
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
    help="Data source: auto (prefer SQLite), sqlite (v1.2.0+), or files (legacy)"
)
@click.pass_context
def sessions(
    ctx: click.Context,
    path: Optional[str],
    output_format: str,
    limit: Optional[int],
    no_group: bool,
    source: str,
):
    """Analyze all OpenCode sessions.

    Supports OpenCode v1.2.0+ SQLite database with hierarchical sub-agent view,
    or legacy file-based storage.

    PATH: Path to directory containing session folders (legacy, optional)
          For v1.2.0+, data is read from SQLite database automatically
    """
    config = ctx.obj["config"]
    console = ctx.obj["console"]

    try:
        analyzer = ctx.obj["analyzer"]
        report_generator = ctx.obj["report_generator"]

        # Get data source info
        source_info = analyzer.get_data_source_info()
        console.print(f"[status.info]Using data source: {source_info['last_used'] or 'auto-detect'}[/status.info]")

        if limit:
            sessions_list = analyzer.analyze_all_sessions(path, limit)
            console.print(f"[status.info]Analyzing {len(sessions_list)} most recent sessions...[/status.info]")
        else:
            sessions_list = analyzer.analyze_all_sessions(path)
            console.print(f"[status.info]Analyzing {len(sessions_list)} sessions...[/status.info]")

        if not sessions_list:
            console.print("[status.error]No sessions found in the specified directory.[/status.error]")
            ctx.exit(1)

        result = report_generator.generate_sessions_summary_report(
            path, limit, output_format, group_workflows=not no_group
        )

        if output_format == "json":
            click.echo(json.dumps(result, indent=2, default=json_serializer))
        elif output_format == "csv":
            click.echo(
                "CSV data would be exported to file. Use 'export' command for file output."
            )

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error analyzing sessions: {error_msg}", err=True)
        if ctx.obj["verbose"]:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


@cli.command()
@click.argument("path", type=click.Path(exists=True), required=False)
@click.option(
    "--interval", "-i", type=int, default=None, help="Update interval in seconds"
)
@click.option("--no-color", is_flag=True, help="Disable colored output")
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
    no_color: bool,
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

    # Disable colors if requested
    if no_color:
        console._color_system = None

    try:
        live_monitor = ctx.obj["live_monitor"]
        interactive_switch = interactive_switch or pick

        # Validate monitoring setup
        validation = live_monitor.validate_monitoring_setup(path if path else None)
        if not validation["valid"]:
            for issue in validation["issues"]:
                console.print(f"[status.error]Error: {issue}[/status.error]")
            ctx.exit(1)

        if validation["warnings"]:
            for warning in validation["warnings"]:
                console.print(f"[status.warning]Warning: {warning}[/status.warning]")

        # Determine data source
        sqlite_available = validation["info"]["sqlite"]["available"]
        files_available = validation["info"]["files"].get("available", False)

        # Determine which monitoring method to use
        use_sqlite = (source == "sqlite") or (source == "auto" and sqlite_available)
        use_files = (source == "files") or (source == "auto" and not sqlite_available and files_available)

        if use_sqlite and sqlite_available:
            selected_session_id = session_id
            if pick and not selected_session_id:
                selected_session_id = live_monitor.pick_sqlite_workflow()
                if not selected_session_id:
                    console.print("[status.warning]No workflow selected. Exiting.[/status.warning]")
                    return
            # Use SQLite workflow monitoring (v1.2.0+)
            live_monitor.start_sqlite_workflow_monitoring(
                interval,
                selected_session_id=selected_session_id,
                interactive_switch=interactive_switch,
            )
        elif use_files and files_available:
            # Use file-based workflow monitoring (legacy)
            if not path:
                path = config.paths.messages_dir
            selected_session_id = session_id
            if pick and not selected_session_id:
                selected_session_id = live_monitor.pick_file_workflow(path)
                if not selected_session_id:
                    console.print("[status.warning]No workflow selected. Exiting.[/status.warning]")
                    return
            console.print("[status.success]Starting workflow live dashboard (legacy file mode)[/status.success]")
            console.print(f"[status.info]Monitoring: {path}[/status.info]")
            console.print(f"[status.info]Update interval: {interval}s[/status.info]")
            live_monitor.start_monitoring(
                path,
                interval,
                selected_session_id=selected_session_id,
                interactive_switch=interactive_switch,
            )
        else:
            console.print("[status.error]No data source available. Please check OpenCode installation.[/status.error]")
            ctx.exit(1)

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
    config = ctx.obj["config"]

    if not path:
        path = config.paths.messages_dir

    try:
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_daily_report(
            path, month, output_format, breakdown
        )

        if output_format == "json":
            click.echo(json.dumps(result, indent=2, default=json_serializer))
        elif output_format == "csv":
            click.echo(
                "CSV data would be exported to file. Use 'export' command for file output."
            )

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error generating daily breakdown: {error_msg}", err=True)
        if ctx.obj["verbose"]:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


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
    config = ctx.obj["config"]

    if not path:
        path = config.paths.messages_dir

    # Convert day name to weekday number
    from .utils.time_utils import WEEKDAY_MAP

    week_start_day = WEEKDAY_MAP[start_day.lower()]

    try:
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_weekly_report(
            path, year, output_format, breakdown, week_start_day
        )

        if output_format == "json":
            click.echo(json.dumps(result, indent=2, default=json_serializer))
        elif output_format == "csv":
            click.echo(
                "CSV data would be exported to file. Use 'export' command for file output."
            )

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error generating weekly breakdown: {error_msg}", err=True)
        if ctx.obj["verbose"]:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


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
    config = ctx.obj["config"]

    if not path:
        path = config.paths.messages_dir

    try:
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_monthly_report(
            path, year, output_format, breakdown
        )

        if output_format == "json":
            click.echo(json.dumps(result, indent=2, default=json_serializer))
        elif output_format == "csv":
            click.echo(
                "CSV data would be exported to file. Use 'export' command for file output."
            )

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error generating monthly breakdown: {error_msg}", err=True)
        if ctx.obj["verbose"]:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


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
    try:
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_model_detail_report(name, output_format)

        if output_format == "json" and result:
            click.echo(json.dumps(result, indent=2, default=json_serializer))
        elif output_format == "csv" and result:
            click.echo(
                "CSV data would be exported to file. Use 'export' command for file output."
            )

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error generating model detail: {error_msg}", err=True)
        if ctx.obj["verbose"]:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


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
    config = ctx.obj["config"]

    if not path:
        path = config.paths.messages_dir

    try:
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_models_report(
            path, timeframe, start_date, end_date, output_format
        )

        if output_format == "json":
            click.echo(json.dumps(result, indent=2, default=json_serializer))
        elif output_format == "csv":
            click.echo(
                "CSV data would be exported to file. Use 'export' command for file output."
            )

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error generating model breakdown: {error_msg}", err=True)
        if ctx.obj["verbose"]:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


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
    config = ctx.obj["config"]

    if not path:
        path = config.paths.messages_dir

    try:
        report_generator = ctx.obj["report_generator"]
        result = report_generator.generate_projects_report(
            path, timeframe, start_date, end_date, output_format
        )

        if output_format == "json":
            click.echo(json.dumps(result, indent=2, default=json_serializer))
        elif output_format == "csv":
            click.echo(
                "CSV data would be exported to file. Use 'export' command for file output."
            )

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error generating project breakdown: {error_msg}", err=True)
        if ctx.obj["verbose"]:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


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

    if not path:
        path = config.paths.messages_dir

    if not export_format:
        export_format = config.export.default_format

    try:
        report_generator = ctx.obj["report_generator"]
        export_service = ctx.obj["export_service"]

        # Generate report data
        report_data = None
        if report_type == "session":
            report_data = report_generator.generate_single_session_report(path, "json")
        elif report_type == "sessions":
            report_data = report_generator.generate_sessions_summary_report(
                path, None, "table"
            )  # Use 'table' to get raw data
        elif report_type == "daily":
            report_data = report_generator.generate_daily_report(
                path, None, "table"
            )  # Use 'table' to get raw data
        elif report_type == "weekly":
            report_data = report_generator.generate_weekly_report(
                path, None, "table", False, 0
            )  # Use 'table' to get raw data, Monday start
        elif report_type == "monthly":
            report_data = report_generator.generate_monthly_report(
                path, None, "table"
            )  # Use 'table' to get raw data
        elif report_type == "models":
            report_data = report_generator.generate_models_report(
                path, "all", None, None, "table"
            )  # Use 'table' to get raw data
        elif report_type == "projects":
            report_data = report_generator.generate_projects_report(
                path, "all", None, None, "table"
            )  # Use 'table' to get raw data

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

        # Get export summary
        summary = export_service.get_export_summary(output_path)
        console.print(f"[status.success]✅ Export completed successfully![/status.success]")
        console.print(f"[metric.label]File:[/metric.label] [metric.value]{output_path}[/metric.value]")
        console.print(f"[metric.label]Size:[/metric.label] [metric.value]{summary.get('size_human', 'Unknown')}[/metric.value]")
        if "rows" in summary:
            console.print(f"[metric.label]Rows:[/metric.label] [metric.value]{summary['rows']}[/metric.value]")

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error exporting data: {error_msg}", err=True)
        if ctx.obj["verbose"]:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


@cli.group()
def config():
    """Configuration management commands."""
    pass


@config.command("show")
@click.pass_context
def config_show(ctx: click.Context):
    """Show current configuration."""
    try:
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

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error showing configuration: {error_msg}", err=True)


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
@click.pass_context
def agents(ctx: click.Context):
    """List all detected agents and their types.

    Shows built-in and user-defined agents, indicating which are main agents
    (stay in same session) and which are sub-agents (create separate sessions).
    """
    try:
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

    except Exception as e:
        error_msg = create_user_friendly_error(e)
        click.echo(f"Error listing agents: {error_msg}", err=True)
        if ctx.obj["verbose"]:
            click.echo(f"Details: {str(e)}", err=True)
        ctx.exit(1)


def main():
    """Entry point for the CLI application."""
    cli()
