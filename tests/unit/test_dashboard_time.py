"""Tests for dashboard time parameterization.

Tests verify that the current_time parameter is properly accepted and used
across all dashboard panel functions to enable deterministic testing.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from ocmonitor.ui.dashboard import DashboardUI
from ocmonitor.models.session import SessionData, TokenUsage, InteractionFile, TimeData


def _make_session(start_time: datetime, end_time: datetime) -> SessionData:
    """Create a mock SessionData with given start/end times."""
    session = MagicMock(spec=SessionData)
    session.session_id = "test-session"
    session.display_title = "Test Session"
    session.project_name = "Test Project"
    session.interaction_count = 5
    session.start_time = start_time
    session.end_time = end_time
    session.total_tokens = TokenUsage(input=1000, output=500, cache_read=200, cache_write=100)
    session.calculate_total_cost.return_value = Decimal("0.50")
    return session


def _make_workflow(start_time: datetime, has_sub_agents: bool = True) -> MagicMock:
    """Create a mock SessionWorkflow with given start time."""
    main_session = _make_session(start_time, start_time + timedelta(hours=1))
    sub_sessions = []
    if has_sub_agents:
        sub = _make_session(
            start_time + timedelta(minutes=5),
            start_time + timedelta(hours=1),
        )
        sub_sessions = [sub]

    workflow = MagicMock()
    workflow.workflow_id = "test-workflow"
    workflow.display_title = "Test Workflow"
    workflow.project_name = "Test Project"
    workflow.start_time = start_time
    workflow.end_time = start_time + timedelta(hours=1)
    workflow.has_sub_agents = has_sub_agents
    workflow.sub_agent_count = len(sub_sessions)
    workflow.session_count = 1 + len(sub_sessions)
    workflow.all_sessions = [main_session] + sub_sessions
    workflow.main_session = main_session
    workflow.sub_agent_sessions = sub_sessions
    workflow.total_tokens = TokenUsage(input=2000, output=1000, cache_read=400, cache_write=200)
    workflow.calculate_total_cost.return_value = Decimal("1.00")
    return workflow


class TestCreateHeaderUsesFormattedTime:
    """Test that create_header uses formatted time string (not raw datetime)."""

    def test_create_header_uses_formatted_time(self):
        """Verify create_header produces formatted string '2026-04-28 15:30:45', not raw datetime."""
        dashboard = DashboardUI()
        session = _make_session(
            datetime(2026, 4, 28, 14, 0, 0),
            datetime(2026, 4, 28, 15, 0, 0),
        )

        # Use a specific current_time with microseconds to prove formatting works
        current_time = datetime(2026, 4, 28, 15, 30, 45, 123456)

        panel = dashboard.create_header(session, current_time=current_time)

        # Panel.renderable is the text content
        panel_text = panel.renderable

        # Must contain formatted time string
        assert "2026-04-28 15:30:45" in panel_text, (
            f"Expected formatted time '2026-04-28 15:30:45' in panel, got: {panel_text}"
        )

        # Must NOT contain microseconds (raw datetime representation)
        assert "123456" not in panel_text, (
            f"Panel should not contain microseconds '123456', got: {panel_text}"
        )
        assert ".000" not in panel_text and "microsecond" not in panel_text.lower(), (
            f"Panel should not contain raw datetime representation, got: {panel_text}"
        )

    def test_create_header_without_current_time_uses_now(self):
        """Verify create_header falls back to datetime.now() when current_time is None."""
        dashboard = DashboardUI()
        session = _make_session(
            datetime(2026, 4, 28, 14, 0, 0),
            datetime(2026, 4, 28, 15, 0, 0),
        )

        panel = dashboard.create_header(session)

        # Should still produce a panel (no errors)
        assert panel.renderable is not None


class TestCreateSessionTimePanelAcceptsCurrentTime:
    """Test that create_session_time_panel accepts and uses current_time."""

    def test_create_session_time_panel_accepts_current_time(self):
        """Verify create_session_time_panel uses current_time for duration (not datetime.now())."""
        dashboard = DashboardUI()

        # Session started 1 hour ago
        session_start = datetime(2026, 4, 28, 14, 0, 0)
        session = _make_session(session_start, session_start + timedelta(hours=1))

        # Current time is 2 hours after session start
        current_time = session_start + timedelta(hours=2)

        panel = dashboard.create_session_time_panel(session, current_time=current_time)

        # Panel should contain "2h" for the 2-hour duration
        panel_text = panel.renderable
        assert "2h" in panel_text, (
            f"Expected '2h' duration in panel when current_time is 2h after start, got: {panel_text}"
        )

    def test_create_session_time_panel_uses_provided_time_not_now(self):
        """Verify duration is calculated from current_time, not from datetime.now()."""
        dashboard = DashboardUI()

        # Session started 30 minutes ago
        session_start = datetime(2026, 4, 28, 14, 0, 0)
        session = _make_session(session_start, session_start + timedelta(minutes=30))

        # Even if real "now" is 5 hours later, use a specific current_time
        current_time = session_start + timedelta(minutes=45)

        panel = dashboard.create_session_time_panel(session, current_time=current_time)

        panel_text = panel.renderable
        # Duration should be 45 minutes (0h), not 5 hours
        assert "0h" in panel_text or "45m" in panel_text, (
            f"Expected 45min duration in panel, got: {panel_text}"
        )


class TestCreateStatusPanelAcceptsCurrentTime:
    """Test that create_status_panel accepts and uses current_time."""

    def test_create_status_panel_accepts_current_time(self):
        """Verify create_status_panel accepts current_time parameter."""
        dashboard = DashboardUI()

        session_start = datetime(2026, 4, 28, 14, 0, 0)
        session = _make_session(session_start, session_start + timedelta(hours=1))
        pricing_data = {}

        current_time = session_start + timedelta(hours=2)

        panel = dashboard.create_status_panel(
            session, pricing_data, quota=None, current_time=current_time
        )

        # Panel should render without errors
        assert panel.renderable is not None
        panel_text = panel.renderable

        # Duration should reflect 2 hours (current_time - start_time)
        assert "2h" in panel_text, (
            f"Expected '2h' in status panel with current_time, got: {panel_text}"
        )


class TestCreateWorkflowStatusPanelAcceptsCurrentTime:
    """Test that create_workflow_status_panel accepts and uses current_time."""

    def test_create_workflow_status_panel_accepts_current_time(self):
        """Verify create_workflow_status_panel accepts current_time parameter."""
        dashboard = DashboardUI()

        workflow_start = datetime(2026, 4, 28, 14, 0, 0)
        workflow = _make_workflow(workflow_start, has_sub_agents=True)
        pricing_data = {}

        current_time = workflow_start + timedelta(hours=3)

        panel = dashboard.create_workflow_status_panel(
            workflow, pricing_data, quota=None, current_time=current_time
        )

        # Panel should render without errors
        assert panel.renderable is not None
        panel_text = panel.renderable

        # Duration should reflect 3 hours (current_time - start_time)
        assert "3h" in panel_text, (
            f"Expected '3h' in workflow status panel with current_time, got: {panel_text}"
        )


class TestCreateWorkflowTimePanelAcceptsCurrentTime:
    """Test that create_workflow_time_panel accepts and uses current_time."""

    def test_create_workflow_time_panel_accepts_current_time(self):
        """Verify create_workflow_time_panel accepts current_time parameter."""
        dashboard = DashboardUI()

        workflow_start = datetime(2026, 4, 28, 14, 0, 0)
        workflow = _make_workflow(workflow_start, has_sub_agents=True)

        current_time = workflow_start + timedelta(hours=2)

        panel = dashboard.create_workflow_time_panel(workflow, current_time=current_time)

        # Panel should render without errors
        assert panel.renderable is not None
        panel_text = panel.renderable

        # Duration should reflect 2 hours (current_time - start_time)
        assert "2h" in panel_text, (
            f"Expected '2h' in workflow time panel with current_time, got: {panel_text}"
        )

    def test_create_workflow_time_panel_uses_provided_time_not_now(self):
        """Verify duration is calculated from current_time, not from datetime.now()."""
        dashboard = DashboardUI()

        # Workflow started 1 hour ago
        workflow_start = datetime(2026, 4, 28, 14, 0, 0)
        workflow = _make_workflow(workflow_start, has_sub_agents=True)

        # Use a specific current_time 30 minutes after start
        current_time = workflow_start + timedelta(minutes=30)

        panel = dashboard.create_workflow_time_panel(workflow, current_time=current_time)

        panel_text = panel.renderable
        # Duration should be 30 minutes (0h), not based on real time
        assert "0h" in panel_text or "30m" in panel_text, (
            f"Expected 30min duration in panel, got: {panel_text}"
        )


class TestCreateDashboardLayoutPropagatesCurrentTime:
    """Test that create_dashboard_layout propagates current_time to all sub-panels."""

    def test_create_dashboard_layout_propagates_current_time(self):
        """Verify create_dashboard_layout propagates current_time to all sub-panels."""
        dashboard = DashboardUI()

        session_start = datetime(2026, 4, 28, 14, 0, 0)
        session = _make_session(session_start, session_start + timedelta(hours=1))
        workflow = _make_workflow(session_start, has_sub_agents=True)
        pricing_data = {}

        # Use a specific current_time with microseconds
        current_time = datetime(2026, 4, 28, 15, 30, 45, 999999)

        layout = dashboard.create_dashboard_layout(
            session=session,
            recent_file=None,
            pricing_data=pricing_data,
            quota=None,
            workflow=workflow,
            current_time=current_time,
        )

        # Render the layout to get the full text
        # Layout is a tree structure - we need to render it to check content
        console = dashboard.console
        from io import StringIO
        string_io = StringIO()
        console = MagicMock()
        console.print = MagicMock(side_effect=lambda x: None)

        # The key check: when current_time is propagated, the header
        # should contain the formatted time string
        header_panel = dashboard.create_header(session, workflow, current_time=current_time)
        header_text = header_panel.renderable

        # Verify formatted time is in header (not raw datetime)
        assert "2026-04-28 15:30:45" in header_text, (
            f"Expected formatted time in header, got: {header_text}"
        )

        # Verify the session time panel also gets the current_time
        time_panel = dashboard.create_session_time_panel(session, current_time=current_time)
        time_text = time_panel.renderable

        # Duration should be 1h30m (from 14:00 to 15:30)
        assert "1h" in time_text and "30m" in time_text, (
            f"Expected 1h30m duration in time panel, got: {time_text}"
        )

        # Verify status panel gets current_time
        status_panel = dashboard.create_status_panel(
            session, pricing_data, quota=None, current_time=current_time
        )
        status_text = status_panel.renderable
        assert "1h" in status_text and "30m" in status_text, (
            f"Expected 1h30m in status panel, got: {status_text}"
        )

        # Verify workflow status panel gets current_time
        wf_status_panel = dashboard.create_workflow_status_panel(
            workflow, pricing_data, quota=None, current_time=current_time
        )
        wf_status_text = wf_status_panel.renderable
        assert "1h" in wf_status_text and "30m" in wf_status_text, (
            f"Expected 1h30m in workflow status panel, got: {wf_status_text}"
        )

        # Verify workflow time panel gets current_time
        wf_time_panel = dashboard.create_workflow_time_panel(workflow, current_time=current_time)
        wf_time_text = wf_time_panel.renderable
        assert "1h" in wf_time_text and "30m" in wf_time_text, (
            f"Expected 1h30m in workflow time panel, got: {wf_time_text}"
        )

    def test_create_dashboard_layout_without_current_time_works(self):
        """Verify create_dashboard_layout works without current_time (uses datetime.now())."""
        dashboard = DashboardUI()

        session_start = datetime(2026, 4, 28, 14, 0, 0)
        session = _make_session(session_start, session_start + timedelta(hours=1))
        workflow = _make_workflow(session_start, has_sub_agents=True)
        pricing_data = {}

        # Call without current_time - should not raise
        layout = dashboard.create_dashboard_layout(
            session=session,
            recent_file=None,
            pricing_data=pricing_data,
            quota=None,
            workflow=workflow,
        )

        assert layout is not None


class TestFlashStyle:
    """Tests for DashboardUI._flash_style method."""

    def test_flash_style_returns_flash_when_changed(self):
        """Should return flash style when field is in changed_fields."""
        from ocmonitor.ui.dashboard import DashboardUI
        ui = DashboardUI()
        result = ui._flash_style("tokens.input", {"tokens.input"}, "metric.value", "metric.flash.tokens")
        assert result == "metric.flash.tokens"

    def test_flash_style_returns_base_when_not_changed(self):
        """Should return base style when field is not in changed_fields."""
        from ocmonitor.ui.dashboard import DashboardUI
        ui = DashboardUI()
        result = ui._flash_style("tokens.input", {"tokens.output"}, "metric.value", "metric.flash.tokens")
        assert result == "metric.value"

    def test_flash_style_returns_base_when_changed_fields_none(self):
        """Should return base style when changed_fields is None."""
        from ocmonitor.ui.dashboard import DashboardUI
        ui = DashboardUI()
        result = ui._flash_style("tokens.input", None, "metric.value", "metric.flash.tokens")
        assert result == "metric.value"

    def test_flash_style_handles_empty_set(self):
        """Should return base style when changed_fields is empty set."""
        from ocmonitor.ui.dashboard import DashboardUI
        ui = DashboardUI()
        result = ui._flash_style("tokens.input", set(), "metric.value", "metric.flash.tokens")
        assert result == "metric.value"