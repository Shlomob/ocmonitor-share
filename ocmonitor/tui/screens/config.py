"""Config screen (read-only)."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label, Static


class ConfigPanel(Static):
    """Panel showing current configuration (read-only)."""

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="detail-panel"):
            yield Label("Configuration", classes="detail-section-title")
            yield Static(id="config-info")

    def on_mount(self) -> None:
        self._update_view()

    def _update_view(self) -> None:
        app = self.app
        cfg = app.config

        source_info = app.data_loader.get_source_info()
        sqlite_status = "available" if source_info["sqlite"]["available"] else "not found"
        files_status = "available" if source_info["files"]["available"] else "not found"

        info = (
            f"Paths\n"
            f"  Database:     {cfg.paths.database_file}\n"
            f"  Messages Dir: {cfg.paths.messages_dir}\n"
            f"  Export Dir:   {cfg.paths.export_dir}\n"
            f"\n"
            f"UI\n"
            f"  Table Style:    {cfg.ui.table_style}\n"
            f"  Theme:          {cfg.ui.theme}\n"
            f"  Progress Bars:  {cfg.ui.progress_bars}\n"
            f"  Colors:         {cfg.ui.colors}\n"
            f"  Live Refresh:   {cfg.ui.live_refresh_interval}s\n"
            f"\n"
            f"Export\n"
            f"  Default Format:    {cfg.export.default_format}\n"
            f"  Include Metadata:  {cfg.export.include_metadata}\n"
            f"\n"
            f"Models\n"
            f"  Config File:       {cfg.models.config_file}\n"
            f"  Remote Fallback:   {cfg.models.remote_fallback}\n"
            f"  Configured Models: {len(app.pricing_data)}\n"
            f"\n"
            f"Data Sources\n"
            f"  SQLite: {sqlite_status} ({source_info['sqlite'].get('path', '-')})\n"
            f"  Files:  {files_status} ({source_info['files'].get('path', '-')})\n"
            f"\n"
            f"Runtime\n"
            f"  No Remote: {app.no_remote}\n"
        )
        self.query_one("#config-info", Static).update(info)
