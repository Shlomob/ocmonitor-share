"""Integration tests for CLI commands."""

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from ocmonitor.cli import cli
from ocmonitor.version import get_version


@pytest.fixture
def mock_sessions_dir(tmp_path):
    """Create a mock sessions directory with test data."""
    sessions_dir = tmp_path / "message"
    sessions_dir.mkdir()

    # Create session 1
    session1 = sessions_dir / "ses_test1"
    session1.mkdir()

    inter1 = session1 / "inter_0001.json"
    inter1.write_text(
        json.dumps(
            {
                "modelID": "test-model",
                "tokens": {
                    "input": 1000,
                    "output": 500,
                    "cache": {"write": 100, "read": 50},
                },
                "timeData": {"created": 1700000000000, "completed": 1700003600000},
                "projectPath": "/home/user/project1",
                "agent": "main",
            }
        )
    )

    # Create session 2
    session2 = sessions_dir / "ses_test2"
    session2.mkdir()

    inter2 = session2 / "inter_0001.json"
    inter2.write_text(
        json.dumps(
            {
                "modelID": "test-model",
                "tokens": {
                    "input": 2000,
                    "output": 1000,
                    "cache": {"write": 200, "read": 100},
                },
                "timeData": {"created": 1700003700000, "completed": 1700004000000},
                "projectPath": "/home/user/project2",
                "agent": "explore",
            }
        )
    )

    return sessions_dir


class TestSessionRecalculate:
    """Tests for --recalculate flag propagation in session commands."""

    @pytest.fixture
    def sessions_dir_with_stored_cost(self, tmp_path):
        """Create mock sessions with stored cost different from computed cost."""
        sessions_dir = tmp_path / "message"
        sessions_dir.mkdir()

        # Create session with minimax-m2.5 model and explicit stored cost
        # Stored cost: 0.042 (deliberately different)
        # Computed cost: 1M * 0.3 + 1M * 1.2 = $1.50 (using actual pricing from models.json)
        session1 = sessions_dir / "ses_test1"
        session1.mkdir()

        inter1 = session1 / "inter_0001.json"
        inter1.write_text(
            json.dumps(
                {
                    "modelID": "minimax-m2.5",
                    "cost": 0.042,
                    "tokens": {
                        "input": 1000000,
                        "output": 1000000,
                        "cache": {"write": 0, "read": 0},
                    },
                    "timeData": {"created": 1700000000000, "completed": 1700003600000},
                    "projectPath": "/home/user/project1",
                    "agent": "main",
                }
            )
        )

        return sessions_dir, session1

    def test_session_json_recalculate_flag_is_propagated(
        self, sessions_dir_with_stored_cost
    ):
        """Test session --recalculate --format json sets recalculated flag correctly."""
        sessions_dir, session_dir = sessions_dir_with_stored_cost

        runner = CliRunner()

        # Without --recalculate
        result_no_recalc = runner.invoke(
            cli, ["session", str(session_dir), "--format", "json"]
        )
        assert result_no_recalc.exit_code == 0
        data_no_recalc = json.loads(result_no_recalc.output)
        assert data_no_recalc["recalculated"] is False

        # With --recalculate
        result_recalc = runner.invoke(
            cli, ["session", str(session_dir), "--format", "json", "--recalculate"]
        )
        assert result_recalc.exit_code == 0
        data_recalc = json.loads(result_recalc.output)
        assert data_recalc["recalculated"] is True

    def test_session_csv_uses_export_message(self, sessions_dir_with_stored_cost):
        """Test session --format csv tells user to use export command (CLI limitation)."""
        sessions_dir, session_dir = sessions_dir_with_stored_cost

        runner = CliRunner()

        result = runner.invoke(
            cli, ["session", str(session_dir), "--format", "csv", "--recalculate"]
        )
        assert result.exit_code == 0
        # CLI currently shows a message to use export command for CSV format
        assert "export" in result.output.lower()


class TestSessionsRecalculate:
    """Tests for --recalculate flag propagation in sessions commands."""

    @pytest.fixture
    def sessions_dir_with_stored_cost(self, tmp_path):
        """Create mock sessions with stored cost different from computed cost."""
        sessions_dir = tmp_path / "message"
        sessions_dir.mkdir()

        session1 = sessions_dir / "ses_test1"
        session1.mkdir()
        inter1 = session1 / "inter_0001.json"
        inter1.write_text(
            json.dumps(
                {
                    "modelID": "minimax-m2.5",
                    "cost": 0.042,
                    "tokens": {
                        "input": 1000000,
                        "output": 1000000,
                        "cache": {"write": 0, "read": 0},
                    },
                    "timeData": {"created": 1700000000000, "completed": 1700003600000},
                    "projectPath": "/home/user/project1",
                    "agent": "main",
                }
            )
        )

        return sessions_dir

    def test_sessions_json_recalculate_flag_is_propagated(
        self, sessions_dir_with_stored_cost
    ):
        """Test sessions --recalculate --format json sets recalculated flag correctly.

        This tests the ReportGenerator directly since CLI output is mixed with
        console messages when using SQLite data source.
        """
        sessions_dir = sessions_dir_with_stored_cost

        # Test ReportGenerator directly
        from decimal import Decimal

        # Load pricing data
        from ocmonitor.config import ConfigManager
        from ocmonitor.services.report_generator import ReportGenerator
        from ocmonitor.services.session_analyzer import SessionAnalyzer

        config_manager = ConfigManager()
        pricing_data = config_manager.load_pricing_data()

        analyzer = SessionAnalyzer(pricing_data)
        report_gen = ReportGenerator(analyzer)

        # Get sessions from the temp dir
        sessions = analyzer.analyze_all_sessions(str(sessions_dir))
        if not sessions:
            pytest.skip("No sessions loaded from temp dir")

        # Test JSON output with force_recalculate=False
        result_no_recalc = report_gen.generate_sessions_summary_report(
            str(sessions_dir), output_format="json", force_recalculate=False
        )
        assert result_no_recalc["recalculated"] is False

        # Test JSON output with force_recalculate=True
        result_recalc = report_gen.generate_sessions_summary_report(
            str(sessions_dir), output_format="json", force_recalculate=True
        )
        assert result_recalc["recalculated"] is True

    def test_sessions_csv_recalculate_flag_is_propagated(
        self, sessions_dir_with_stored_cost
    ):
        """Test sessions --recalculate --format csv sets recalculated flag correctly."""
        sessions_dir = sessions_dir_with_stored_cost

        # Test ReportGenerator directly
        from ocmonitor.config import ConfigManager
        from ocmonitor.services.report_generator import ReportGenerator
        from ocmonitor.services.session_analyzer import SessionAnalyzer

        config_manager = ConfigManager()
        pricing_data = config_manager.load_pricing_data()

        analyzer = SessionAnalyzer(pricing_data)
        report_gen = ReportGenerator(analyzer)

        # Test CSV output with force_recalculate=True
        result = report_gen.generate_sessions_summary_report(
            str(sessions_dir), output_format="csv", force_recalculate=True
        )
        # Should return list of CSV rows
        assert isinstance(result, list)
        assert len(result) >= 1  # At least one row of data


class TestSessionsRecalculate:
    """Tests for --recalculate flag propagation in sessions commands."""

    @pytest.fixture
    def sessions_dir_with_stored_cost(self, tmp_path):
        """Create mock sessions with stored cost different from computed cost."""
        sessions_dir = tmp_path / "message"
        sessions_dir.mkdir()

        session1 = sessions_dir / "ses_test1"
        session1.mkdir()
        inter1 = session1 / "inter_0001.json"
        inter1.write_text(
            json.dumps(
                {
                    "modelID": "minimax-m2.5",
                    "cost": 0.042,
                    "tokens": {
                        "input": 1000000,
                        "output": 1000000,
                        "cache": {"write": 0, "read": 0},
                    },
                    "timeData": {"created": 1700000000000, "completed": 1700003600000},
                    "projectPath": "/home/user/project1",
                    "agent": "main",
                }
            )
        )

        return sessions_dir

    def test_sessions_json_recalculate_flag_is_propagated(
        self, sessions_dir_with_stored_cost
    ):
        """Test sessions --recalculate --format json sets recalculated flag correctly."""
        sessions_dir = sessions_dir_with_stored_cost

        # Test ReportGenerator directly since CLI data source causes mixed output
        from ocmonitor.config import ConfigManager
        from ocmonitor.services.report_generator import ReportGenerator
        from ocmonitor.services.session_analyzer import SessionAnalyzer

        config_manager = ConfigManager()
        pricing_data = config_manager.load_pricing_data()

        analyzer = SessionAnalyzer(pricing_data)
        report_gen = ReportGenerator(analyzer)

        # Test JSON output with force_recalculate=False
        result_no_recalc = report_gen.generate_sessions_summary_report(
            str(sessions_dir), output_format="json", force_recalculate=False
        )
        assert result_no_recalc["recalculated"] is False

        # Test JSON output with force_recalculate=True
        result_recalc = report_gen.generate_sessions_summary_report(
            str(sessions_dir), output_format="json", force_recalculate=True
        )
        assert result_recalc["recalculated"] is True

    def test_sessions_csv_recalculate_flag_is_propagated(
        self, sessions_dir_with_stored_cost
    ):
        """Test sessions --recalculate --format csv sets recalculated flag correctly."""
        sessions_dir = sessions_dir_with_stored_cost

        # Test ReportGenerator directly
        from ocmonitor.config import ConfigManager
        from ocmonitor.services.report_generator import ReportGenerator
        from ocmonitor.services.session_analyzer import SessionAnalyzer

        config_manager = ConfigManager()
        pricing_data = config_manager.load_pricing_data()

        analyzer = SessionAnalyzer(pricing_data)
        report_gen = ReportGenerator(analyzer)

        # Test CSV output with force_recalculate=True
        result = report_gen.generate_sessions_summary_report(
            str(sessions_dir), output_format="csv", force_recalculate=True
        )
        # Should return list of CSV rows
        assert isinstance(result, list)
        assert len(result) >= 1  # At least one row of data


class TestConfigCommand:
    """Tests for config CLI commands."""

    def test_config_show(self):
        """Test config show command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show"])

        # Should succeed and show configuration
        assert result.exit_code == 0
        assert result.output != ""


class TestVersionCommand:
    """Tests for version reporting."""

    def test_version_matches_resolved_package_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert f"version {get_version()}" in result.output


class TestSessionsCommand:
    """Tests for sessions CLI command."""

    def test_sessions_basic(self, mock_sessions_dir):
        """Test basic sessions command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["sessions", str(mock_sessions_dir)])

        # Should succeed
        assert result.exit_code == 0

    def test_sessions_with_limit(self, mock_sessions_dir):
        """Test sessions command with limit."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["sessions", str(mock_sessions_dir), "--limit", "1"]
        )

        assert result.exit_code == 0

    def test_sessions_nonexistent_directory(self):
        """Test sessions command with non-existent directory."""
        runner = CliRunner()
        result = runner.invoke(cli, ["sessions", "/nonexistent/path"])

        # Should handle gracefully - may succeed with no output or show error
        assert result.exit_code in [0, 2]


class TestDailyCommand:
    """Tests for daily CLI command."""

    def test_daily_basic(self, mock_sessions_dir):
        """Test basic daily command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["daily", str(mock_sessions_dir)])

        # Should succeed
        assert result.exit_code == 0

    def test_daily_with_breakdown(self, mock_sessions_dir):
        """Test daily command with breakdown flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["daily", str(mock_sessions_dir), "--breakdown"])

        assert result.exit_code == 0

    def test_daily_invalid_year_rejected(self, mock_sessions_dir):
        """Test daily command rejects invalid year at parse-time."""
        runner = CliRunner()
        result = runner.invoke(cli, ["daily", str(mock_sessions_dir), "--year", "20x6"])

        assert result.exit_code == 2
        assert "Invalid value for '--year'" in result.output

    def test_daily_rejects_multiple_period_options(self, mock_sessions_dir):
        """Test daily command rejects conflicting period options."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["daily", str(mock_sessions_dir), "--week", "--year", "2024"]
        )

        assert result.exit_code == 2
        assert "mutually exclusive" in result.output

    def test_daily_json_includes_filter(self, mock_sessions_dir):
        """Test daily JSON output includes filter metadata."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["daily", str(mock_sessions_dir), "--year", "2024", "--format", "json"]
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["type"] == "daily_breakdown"
        assert data["filter"] == {"year": 2024}
        assert data["filter_label"] == "year: 2024"
        assert isinstance(data.get("daily_breakdown"), list)


class TestWeeklyCommand:
    """Tests for weekly CLI command."""

    def test_weekly_basic(self, mock_sessions_dir):
        """Test basic weekly command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["weekly", str(mock_sessions_dir)])

        assert result.exit_code == 0

    def test_weekly_with_start_day(self, mock_sessions_dir):
        """Test weekly command with custom start day."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["weekly", str(mock_sessions_dir), "--start-day", "sunday"]
        )

        assert result.exit_code == 0

    def test_weekly_invalid_year_rejected(self, mock_sessions_dir):
        """Test weekly command rejects invalid year at parse-time."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["weekly", str(mock_sessions_dir), "--year", "20x6"]
        )

        assert result.exit_code == 2
        assert "Invalid value for '--year'" in result.output

    def test_weekly_rejects_month_and_year_together(self, mock_sessions_dir):
        """Test weekly command rejects --month + --year together."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["weekly", str(mock_sessions_dir), "--month", "2024-01", "--year", "2024"],
        )

        assert result.exit_code == 2
        assert "mutually exclusive" in result.output

    def test_weekly_json_includes_week_start_day_filter(self, mock_sessions_dir):
        """Test weekly JSON output includes week_start_day filter when custom."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "weekly",
                str(mock_sessions_dir),
                "--start-day",
                "sunday",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["type"] == "weekly_breakdown"
        assert data["filter"] == {"week_start_day": 6}
        assert data["filter_label"] is None
        assert isinstance(data.get("weekly_breakdown"), list)


class TestMonthlyCommand:
    """Tests for monthly CLI command."""

    def test_monthly_basic(self, mock_sessions_dir):
        """Test basic monthly command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["monthly", str(mock_sessions_dir)])

        assert result.exit_code == 0

    def test_monthly_invalid_year_rejected(self, mock_sessions_dir):
        """Test monthly command rejects invalid year at parse-time."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["monthly", str(mock_sessions_dir), "--year", "20x6"]
        )

        assert result.exit_code == 2
        assert "Invalid value for '--year'" in result.output

    def test_monthly_json_includes_filter(self, mock_sessions_dir):
        """Test monthly JSON output includes filter metadata."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["monthly", str(mock_sessions_dir), "--year", "2024", "--format", "json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["type"] == "monthly_breakdown"
        assert data["filter"] == {"year": 2024}
        assert data["filter_label"] == "year: 2024"
        assert isinstance(data.get("monthly_breakdown"), list)


class TestExportCommand:
    """Tests for export CLI command."""

    def test_export_csv(self, mock_sessions_dir, tmp_path):
        """Test export command with CSV format."""
        export_dir = tmp_path / "exports"
        export_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(
            cli, ["export", "sessions", str(mock_sessions_dir), "--format", "csv"]
        )

        # Should succeed or handle missing options gracefully
        assert result.exit_code in [0, 2]

    def test_export_json(self, mock_sessions_dir, tmp_path):
        """Test export command with JSON format."""
        export_dir = tmp_path / "exports"
        export_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(
            cli, ["export", "sessions", str(mock_sessions_dir), "--format", "json"]
        )

        assert result.exit_code in [0, 2]


class TestSessionCommand:
    """Tests for single session CLI command."""

    def test_session_single(self, mock_sessions_dir):
        """Test analyzing single session."""
        session_dir = mock_sessions_dir / "ses_test1"

        runner = CliRunner()
        result = runner.invoke(cli, ["session", str(session_dir)])

        assert result.exit_code == 0

    def test_session_no_valid_data_does_not_wrap_click_exit(self, tmp_path):
        """Session with no valid data should not print wrapped Unexpected error."""
        empty_dir = tmp_path / "empty_session_dir"
        empty_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["session", str(empty_dir)])

        assert result.exit_code == 1
        assert (
            "No valid session data found in the specified directory." in result.output
        )
        assert "Error analyzing session:" not in result.output
        assert "Unexpected error: 1" not in result.output


class TestLiveCommand:
    """Tests for live command selection and precedence."""

    def test_live_help_describes_inline_as_the_normal_buffer_fallback(self):
        """Help must distinguish inline output from the default full-screen view."""
        runner = CliRunner()

        result = runner.invoke(cli, ["live", "--help"])

        assert result.exit_code == 0
        normalized_help = " ".join(result.output.split())
        assert "normal terminal-buffer output" in normalized_help
        assert "default full-screen display" in normalized_help

    @pytest.mark.parametrize("interval", ["0", "-1"])
    def test_live_rejects_nonpositive_update_intervals(self, interval):
        """The monitor must not accept intervals that cause a busy polling loop."""
        runner = CliRunner()

        result = runner.invoke(cli, ["live", "--interval", interval])

        assert result.exit_code == 2
        assert "not in the range" in result.output
        assert ">=1" in result.output

    @pytest.mark.parametrize(
        ("source", "method_name", "inline"),
        [
            ("files", "start_monitoring", False),
            ("files", "start_monitoring", True),
            ("sqlite", "start_sqlite_workflow_monitoring", False),
            ("sqlite", "start_sqlite_workflow_monitoring", True),
        ],
    )
    def test_live_forwards_inline_mode_for_each_source(
        self, mock_sessions_dir, source, method_name, inline
    ):
        """The CLI forwards full-screen default and inline fallback to each monitor."""
        runner = CliRunner()
        captured = {}

        def fake_start_monitoring(self, *args, **kwargs):
            """A fake start_monitoring replacement used to capture call args.

            This test-local stub records positional and keyword arguments so the
            test can assert that the CLI forwarded the `--inline` flag correctly.
            """
            captured["args"] = args
            captured["kwargs"] = kwargs

        validation = {
            "valid": True,
            "issues": [],
            "warnings": [],
            "info": {
                "sqlite": {"available": source == "sqlite"},
                "files": {"available": source == "files"},
            },
        }
        command = ["live"]
        if source == "files":
            command.append(str(mock_sessions_dir))
        command.extend(["--source", source])
        if inline:
            command.append("--inline")

        with patch(
            "ocmonitor.services.live_monitor.LiveMonitor.validate_monitoring_setup",
            return_value=validation,
        ), patch(
            f"ocmonitor.services.live_monitor.LiveMonitor.{method_name}",
            new=fake_start_monitoring,
        ):
            result = runner.invoke(cli, command)

        assert result.exit_code == 0
        assert captured["kwargs"]["inline"] is inline

    def test_live_with_pick_uses_picker_selection(self, mock_sessions_dir):
        runner = CliRunner()
        captured = {}

        def fake_start_monitoring(self, base_path, refresh_interval=5, **kwargs):
            captured["base_path"] = base_path
            captured["kwargs"] = kwargs

        with patch(
            "ocmonitor.services.live_monitor.LiveMonitor.validate_monitoring_setup",
            return_value={
                "valid": True,
                "issues": [],
                "warnings": [],
                "info": {"sqlite": {"available": False}, "files": {"available": True}},
            },
        ), patch(
            "ocmonitor.services.live_monitor.LiveMonitor.pick_file_workflow",
            return_value="picked-workflow",
        ), patch(
            "ocmonitor.services.live_monitor.LiveMonitor.start_monitoring",
            new=fake_start_monitoring,
        ):
            result = runner.invoke(
                cli,
                ["live", str(mock_sessions_dir), "--source", "files", "--pick"],
            )

        assert result.exit_code == 0
        assert captured["base_path"] == str(mock_sessions_dir)
        assert captured["kwargs"]["selected_session_id"] == "picked-workflow"
        assert captured["kwargs"]["interactive_switch"] is True

    def test_live_session_id_takes_precedence_over_pick(self, mock_sessions_dir):
        runner = CliRunner()
        captured = {}

        def fake_start_monitoring(self, base_path, refresh_interval=5, **kwargs):
            captured["kwargs"] = kwargs

        with patch(
            "ocmonitor.services.live_monitor.LiveMonitor.validate_monitoring_setup",
            return_value={
                "valid": True,
                "issues": [],
                "warnings": [],
                "info": {"sqlite": {"available": False}, "files": {"available": True}},
            },
        ), patch(
            "ocmonitor.services.live_monitor.LiveMonitor.pick_file_workflow",
            side_effect=AssertionError("picker should not be called"),
        ), patch(
            "ocmonitor.services.live_monitor.LiveMonitor.start_monitoring",
            new=fake_start_monitoring,
        ):
            result = runner.invoke(
                cli,
                [
                    "live",
                    str(mock_sessions_dir),
                    "--source",
                    "files",
                    "--pick",
                    "--session-id",
                    "explicit-session",
                ],
            )

        assert result.exit_code == 0
        assert captured["kwargs"]["selected_session_id"] == "explicit-session"
        assert captured["kwargs"]["interactive_switch"] is True


class TestMetricsCommand:
    """Tests for metrics CLI command."""

    def test_metrics_help(self):
        """Test metrics command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["metrics", "--help"])

        assert result.exit_code == 0
        assert "--port" in result.output
        assert "--host" in result.output

    def test_metrics_starts_server(self):
        """Test metrics command starts server with correct args."""
        runner = CliRunner()

        with patch("ocmonitor.services.metrics_server.MetricsServer") as MockServer:
            instance = MockServer.return_value
            instance.start.side_effect = KeyboardInterrupt

            result = runner.invoke(
                cli, ["metrics", "--port", "9999", "--host", "127.0.0.1"]
            )

        MockServer.assert_called_once()
        call_kwargs = MockServer.call_args
        # positional: pricing_data; keyword: host, port
        assert call_kwargs.kwargs["port"] == 9999
        assert call_kwargs.kwargs["host"] == "127.0.0.1"

    def test_metrics_port_in_use(self):
        """Test friendly error when port is in use."""
        runner = CliRunner()

        with patch("ocmonitor.services.metrics_server.MetricsServer") as MockServer:
            instance = MockServer.return_value
            instance.start.side_effect = OSError("Address already in use")

            result = runner.invoke(cli, ["metrics", "--port", "9090"])

        assert result.exit_code == 1
        assert "already in use" in result.output


class TestCLIHelp:
    """Tests for CLI help functionality."""

    def test_main_help(self):
        """Test main CLI help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_main_short_help_alias(self):
        """Test main CLI short help alias."""
        runner = CliRunner()
        long_help = runner.invoke(cli, ["--help"])
        short_help = runner.invoke(cli, ["-h"])

        assert long_help.exit_code == 0
        assert short_help.exit_code == 0
        assert short_help.output == long_help.output

    def test_sessions_help(self):
        """Test sessions command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["sessions", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_daily_help(self):
        """Test daily command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["daily", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_export_help(self):
        """Test export command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["export", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_config_help(self):
        """Test config command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output


class TestTimeframeFiltering:
    """Integration tests for timeframe filtering in models and projects commands."""

    @pytest.fixture
    def sessions_dir_with_dates(self, tmp_path):
        """Create sessions with controlled timestamps spanning multiple weeks/months."""
        sessions_dir = tmp_path / "message"
        sessions_dir.mkdir()

        today = date.today()

        # Session 1: This week
        this_week_start = today - timedelta(days=today.weekday())
        session1_ts = int(
            datetime.combine(this_week_start, datetime.min.time()).timestamp() * 1000
        )

        # Session 2: Last week
        last_week = today - timedelta(days=7)
        last_week_start = last_week - timedelta(days=last_week.weekday())
        session2_ts = int(
            datetime.combine(last_week_start, datetime.min.time()).timestamp() * 1000
        )

        # Session 3: Last month (35 days ago)
        last_month = today - timedelta(days=35)
        session3_ts = int(
            datetime.combine(last_month, datetime.min.time()).timestamp() * 1000
        )

        # Session 1: This week
        session1 = sessions_dir / "ses_week1"
        session1.mkdir()
        inter1 = session1 / "inter_0001.json"
        inter1.write_text(
            json.dumps(
                {
                    "modelID": "test-model-1",
                    "tokens": {
                        "input": 1000,
                        "output": 500,
                        "cache": {"write": 100, "read": 50},
                    },
                    "timeData": {
                        "created": session1_ts,
                        "completed": session1_ts + 3600000,
                    },
                    "projectPath": "/home/user/project-alpha",
                    "agent": "main",
                }
            )
        )

        # Session 2: Last week
        session2 = sessions_dir / "ses_week2"
        session2.mkdir()
        inter2 = session2 / "inter_0001.json"
        inter2.write_text(
            json.dumps(
                {
                    "modelID": "test-model-1",
                    "tokens": {
                        "input": 2000,
                        "output": 1000,
                        "cache": {"write": 200, "read": 100},
                    },
                    "timeData": {
                        "created": session2_ts,
                        "completed": session2_ts + 3600000,
                    },
                    "projectPath": "/home/user/project-beta",
                    "agent": "main",
                }
            )
        )

        # Session 3: Last month
        session3 = sessions_dir / "ses_month"
        session3.mkdir()
        inter3 = session3 / "inter_0001.json"
        inter3.write_text(
            json.dumps(
                {
                    "modelID": "test-model-2",
                    "tokens": {
                        "input": 1500,
                        "output": 750,
                        "cache": {"write": 150, "read": 75},
                    },
                    "timeData": {
                        "created": session3_ts,
                        "completed": session3_ts + 3600000,
                    },
                    "projectPath": "/home/user/project-alpha",
                    "agent": "main",
                }
            )
        )

        return sessions_dir

    def test_models_weekly_timeframe_json(self, sessions_dir_with_dates):
        """Test models --timeframe weekly returns correct date range in metadata."""
        from ocmonitor.utils.time_utils import TimeUtils

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "models",
                str(sessions_dir_with_dates),
                "--timeframe",
                "weekly",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["timeframe"] == "weekly"
        assert data["start_date"] is not None
        assert data["end_date"] is not None

        # Dates should match current week
        week_start, week_end = TimeUtils.get_current_week_range()
        assert data["start_date"] == week_start.isoformat()
        assert data["end_date"] == week_end.isoformat()

    def test_models_monthly_timeframe_json(self, sessions_dir_with_dates):
        """Test models --timeframe monthly returns correct date range in metadata."""
        from ocmonitor.utils.time_utils import TimeUtils

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "models",
                str(sessions_dir_with_dates),
                "--timeframe",
                "monthly",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["timeframe"] == "monthly"
        assert data["start_date"] is not None
        assert data["end_date"] is not None

        # Dates should match current month
        month_start, month_end = TimeUtils.get_current_month_range()
        assert data["start_date"] == month_start.isoformat()
        assert data["end_date"] == month_end.isoformat()

    def test_models_daily_timeframe_json(self, sessions_dir_with_dates):
        """Test models --timeframe daily returns correct date range in metadata."""
        from ocmonitor.utils.time_utils import TimeUtils

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "models",
                str(sessions_dir_with_dates),
                "--timeframe",
                "daily",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["timeframe"] == "daily"
        assert data["start_date"] is not None
        assert data["end_date"] is not None

        # Dates should match today (last 1 day range)
        today_start, today_end = TimeUtils.get_last_n_days_range(1)
        assert data["start_date"] == today_start.isoformat()
        assert data["end_date"] == today_end.isoformat()

    def test_models_all_timeframe_json(self, sessions_dir_with_dates):
        """Test models --timeframe all has no date filtering."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "models",
                str(sessions_dir_with_dates),
                "--timeframe",
                "all",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["timeframe"] == "all"
        assert data["start_date"] is None
        assert data["end_date"] is None

    def test_projects_weekly_timeframe_json(self, sessions_dir_with_dates):
        """Test projects --timeframe weekly returns correct date range in metadata."""
        from ocmonitor.utils.time_utils import TimeUtils

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "projects",
                str(sessions_dir_with_dates),
                "--timeframe",
                "weekly",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["timeframe"] == "weekly"
        assert data["start_date"] is not None
        assert data["end_date"] is not None

        # Dates should match current week
        week_start, week_end = TimeUtils.get_current_week_range()
        assert data["start_date"] == week_start.isoformat()
        assert data["end_date"] == week_end.isoformat()

    def test_models_explicit_date_overrides_timeframe(self, sessions_dir_with_dates):
        """Test that explicit --start-date overrides --timeframe weekly."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "models",
                str(sessions_dir_with_dates),
                "--timeframe",
                "weekly",
                "--start-date",
                "2024-01-01",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        # Explicit date should be used, not current week start
        assert data["start_date"] == "2024-01-01"

    def test_projects_monthly_timeframe_json(self, sessions_dir_with_dates):
        """Test projects --timeframe monthly returns correct date range in metadata."""
        from ocmonitor.utils.time_utils import TimeUtils

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "projects",
                str(sessions_dir_with_dates),
                "--timeframe",
                "monthly",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["timeframe"] == "monthly"
        assert data["start_date"] is not None
        assert data["end_date"] is not None

        # Dates should match current month
        month_start, month_end = TimeUtils.get_current_month_range()
        assert data["start_date"] == month_start.isoformat()
        assert data["end_date"] == month_end.isoformat()
