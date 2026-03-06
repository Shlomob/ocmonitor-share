"""Export modal dialog."""

from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, ContentSwitcher, Label, Select, Static


class ExportModal(ModalScreen[Optional[str]]):
    """Modal for exporting current screen data."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="export-dialog"):
            yield Label("Export Data")
            yield Label("Format:")
            yield Select(
                [("CSV", "csv"), ("JSON", "json")],
                value="csv",
                id="export-format",
            )
            yield Label("Report Type:")
            yield Select(
                [
                    ("Sessions", "sessions"),
                    ("Single Session", "single_session"),
                    ("Daily", "daily"),
                    ("Weekly", "weekly"),
                    ("Monthly", "monthly"),
                    ("Models", "models"),
                    ("Projects", "projects"),
                ],
                value="sessions",
                id="export-type",
            )
            with Horizontal(id="export-buttons"):
                yield Button("Export", variant="primary", id="export-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        contextual = self._find_contextual_data()
        if contextual:
            report_type, _ = contextual
            try:
                type_sel = self.query_one("#export-type", Select)
                type_sel.value = report_type
            except Exception:
                pass

    def _find_contextual_data(self):
        """Walk the screen stack and content switcher for contextual export data."""
        app = self.app
        # Walk screen stack in reverse, skip self (ExportModal)
        for screen in reversed(app.screen_stack):
            if screen is self:
                continue
            if hasattr(screen, "get_export_data"):
                result = screen.get_export_data()
                if result is not None:
                    return result

        # Check ContentSwitcher current panel
        try:
            switcher = app.query_one("#content-switcher", ContentSwitcher)
            if switcher.current:
                panel = app.query_one(f"#{switcher.current}")
                if hasattr(panel, "get_export_data"):
                    result = panel.get_export_data()
                    if result is not None:
                        return result
        except Exception:
            pass

        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-btn":
            self._do_export()
        elif event.button.id == "cancel-btn":
            self.dismiss(None)

    def _do_export(self) -> None:
        format_sel = self.query_one("#export-format", Select)
        type_sel = self.query_one("#export-type", Select)
        fmt = str(format_sel.value)
        report_type = str(type_sel.value)

        app = self.app
        try:
            # Try contextual data first
            contextual = self._find_contextual_data()
            if contextual and contextual[0] == report_type:
                _, report_data = contextual
            else:
                # Fall back to fresh global data
                analyzer = app.analyzer
                sessions = analyzer.analyze_all_sessions()
                report_data = self._build_global_data(analyzer, sessions, report_type)

            output_path = app.export_service.export_report_data(
                report_data, report_type, fmt
            )
            app.notify(f"Exported to {output_path}", severity="information")
            self.dismiss(output_path)

        except Exception as e:
            app.notify(f"Export failed: {e}", severity="error")
            self.dismiss(None)

    @staticmethod
    def _build_global_data(analyzer, sessions, report_type):
        if report_type == "sessions":
            return {"sessions": sessions}
        elif report_type == "single_session":
            return {"sessions": sessions}
        elif report_type == "daily":
            return {"daily_usage": analyzer.create_daily_breakdown(sessions)}
        elif report_type == "weekly":
            return {"weekly_usage": analyzer.create_weekly_breakdown(sessions)}
        elif report_type == "monthly":
            return {"monthly_usage": analyzer.create_monthly_breakdown(sessions)}
        elif report_type == "models":
            return {"model_breakdown": analyzer.create_model_breakdown(sessions)}
        elif report_type == "projects":
            return {"project_breakdown": analyzer.create_project_breakdown(sessions)}
        return {}

    def action_cancel(self) -> None:
        self.dismiss(None)
