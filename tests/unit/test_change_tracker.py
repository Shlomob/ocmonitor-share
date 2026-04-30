"""Unit tests for change tracking utilities."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from ocmonitor.ui.change_tracker import (
    ValueChangeTracker,
    extract_session_metrics,
    extract_workflow_metrics,
)
from ocmonitor.models.session import SessionData, TokenUsage, InteractionFile, TimeData
from ocmonitor.models.workflow import SessionWorkflow


class TestValueChangeTracker:
    """Tests for ValueChangeTracker class."""

    def test_tracker_first_refresh_returns_empty(self):
        """First refresh should return empty set (no previous data)."""
        tracker = ValueChangeTracker()
        result = tracker.update_and_diff({"a": 1, "b": 2})
        assert result == set()

    def test_tracker_detects_token_changes(self):
        """Should detect token value changes."""
        tracker = ValueChangeTracker()
        tracker.update_and_diff({"tokens.input": 100, "tokens.output": 50})
        result = tracker.update_and_diff({"tokens.input": 150, "tokens.output": 50})
        assert "tokens.input" in result
        assert "tokens.output" not in result

    def test_tracker_detects_cost_changes(self):
        """Should detect cost changes."""
        tracker = ValueChangeTracker()
        tracker.update_and_diff({"cost.total": 1.5})
        result = tracker.update_and_diff({"cost.total": 2.0})
        assert "cost.total" in result

    def test_tracker_detects_duration_changes(self):
        """Should detect duration changes."""
        tracker = ValueChangeTracker()
        tracker.update_and_diff({"duration_ms": 1000})
        result = tracker.update_and_diff({"duration_ms": 2000})
        assert "duration_ms" in result

    def test_tracker_returns_empty_when_no_change(self):
        """Should return empty set when no values changed."""
        tracker = ValueChangeTracker()
        tracker.update_and_diff({"a": 1, "b": 2, "c": 3})
        result = tracker.update_and_diff({"a": 1, "b": 2, "c": 3})
        assert result == set()

    def test_tracker_reset_clears_previous_data(self):
        """Reset should clear previous data, making next call return empty set."""
        tracker = ValueChangeTracker()
        tracker.update_and_diff({"a": 1})
        tracker.reset()
        result = tracker.update_and_diff({"a": 100})
        assert result == set()  # First call after reset

    def test_tracker_handles_multiple_changes(self):
        """Should detect multiple field changes at once."""
        tracker = ValueChangeTracker()
        tracker.update_and_diff({
            "tokens.input": 100,
            "tokens.output": 50,
            "cost.total": 1.0,
        })
        result = tracker.update_and_diff({
            "tokens.input": 200,
            "tokens.output": 100,
            "cost.total": 2.0,
        })
        assert result == {"tokens.input", "tokens.output", "cost.total"}

    def test_tracker_handles_new_fields(self):
        """Should detect newly added fields."""
        tracker = ValueChangeTracker()
        tracker.update_and_diff({"a": 1})
        result = tracker.update_and_diff({"a": 1, "b": 2})
        assert "b" in result


def _make_interaction_file(
    created_ms: int,
    completed_ms: int,
    input_tok: int = 100,
    output_tok: int = 50,
    cache_read: int = 20,
    cache_write: int = 10,
) -> InteractionFile:
    """Create a mock InteractionFile with given timing and token data."""
    return InteractionFile(
        file_path=Path("/tmp/test.json"),
        session_id="test-session",
        model_id="test-model",
        tokens=TokenUsage(
            input=input_tok,
            output=output_tok,
            cache_read=cache_read,
            cache_write=cache_write,
        ),
        time_data=TimeData(created=created_ms, completed=completed_ms),
    )


def _make_session_data(
    start_time: datetime,
    end_time: datetime,
    num_interactions: int = 5,
) -> SessionData:
    """Create a SessionData with files that produce the given start/end times."""
    # Create files spaced within the start/end time range
    duration = end_time - start_time
    files = []
    for i in range(num_interactions):
        offset = duration * i / max(1, num_interactions - 1)
        file_start = start_time + offset
        file_end = file_start + timedelta(seconds=10)
        files.append(_make_interaction_file(
            created_ms=int(file_start.timestamp() * 1000),
            completed_ms=int(file_end.timestamp() * 1000),
        ))
    return SessionData(
        session_id="test-session",
        session_path=Path("/tmp/test_session"),
        files=files,
    )


class TestExtractSessionMetrics:
    """Tests for extract_session_metrics function."""

    def test_extract_session_metrics_keys(self):
        """Should return correct metric keys."""
        start = datetime.now() - timedelta(minutes=5)
        end = datetime.now()
        session = _make_session_data(start, end, num_interactions=5)

        pricing_data = {}
        current_time = datetime.now()

        metrics = extract_session_metrics(session, pricing_data, current_time)

        assert "tokens.input" in metrics
        assert "tokens.output" in metrics
        assert "tokens.cache_read" in metrics
        assert "tokens.cache_write" in metrics
        assert "tokens.total" in metrics
        assert "cost.total" in metrics
        assert "duration_ms" in metrics
        assert "interaction_count" in metrics

    def test_extract_session_metrics_duration_calculation(self):
        """Should correctly calculate duration in milliseconds."""
        start = datetime.now() - timedelta(seconds=30)
        end = datetime.now()
        session = _make_session_data(start, end, num_interactions=2)

        current = datetime.now()

        metrics = extract_session_metrics(session, {}, current)

        # Should be approximately 30000ms (30 seconds)
        assert 29000 <= metrics["duration_ms"] <= 31000

    def test_extract_session_metrics_token_values(self):
        """Should correctly extract token values."""
        # Create session with known token values
        start = datetime.now() - timedelta(minutes=1)
        end = datetime.now()

        # Create files with specific tokens
        files = [
            _make_interaction_file(
                created_ms=int(start.timestamp() * 1000),
                completed_ms=int(end.timestamp() * 1000),
                input_tok=1000,
                output_tok=500,
                cache_read=200,
                cache_write=100,
            ),
        ]

        session = SessionData(
            session_id="test",
            session_path=Path("/tmp/test"),
            files=files,
        )

        metrics = extract_session_metrics(session, {}, datetime.now())

        assert metrics["tokens.input"] == 1000
        assert metrics["tokens.output"] == 500
        assert metrics["tokens.cache_read"] == 200
        assert metrics["tokens.cache_write"] == 100
        assert metrics["tokens.total"] == 1800  # 1000 + 500 + 200 + 100


class TestExtractWorkflowMetrics:
    """Tests for extract_workflow_metrics function."""

    def test_extract_workflow_metrics_keys(self):
        """Should return correct metric keys for workflow."""
        start = datetime.now() - timedelta(minutes=5)
        end = datetime.now()

        main_session = _make_session_data(start, end, num_interactions=3)
        sub_session = _make_session_data(
            start + timedelta(minutes=1),
            end - timedelta(minutes=1),
            num_interactions=2,
        )

        workflow = SessionWorkflow(
            workflow_id="test-workflow",
            main_session=main_session,
            sub_agent_sessions=[sub_session],
        )

        pricing_data = {}
        current_time = datetime.now()

        metrics = extract_workflow_metrics(workflow, pricing_data, current_time)

        assert "tokens.input" in metrics
        assert "tokens.output" in metrics
        assert "tokens.cache_read" in metrics
        assert "tokens.cache_write" in metrics
        assert "tokens.total" in metrics
        assert "cost.total" in metrics
        assert "duration_ms" in metrics
        assert "session_count" in metrics
        assert "sub_agent_count" in metrics

    def test_extract_workflow_metrics_aggregates_tokens(self):
        """Should aggregate tokens across main and sub-agent sessions."""
        start = datetime.now() - timedelta(minutes=5)
        end = datetime.now()

        # Main session with specific tokens
        main_session = _make_session_data(start, end, num_interactions=1)
        main_session.files = [
            _make_interaction_file(
                created_ms=int(start.timestamp() * 1000),
                completed_ms=int(end.timestamp() * 1000),
                input_tok=1000,
                output_tok=500,
                cache_read=200,
                cache_write=100,
            ),
        ]

        # Sub-agent session with different tokens
        sub_session = _make_session_data(
            start + timedelta(minutes=1),
            end - timedelta(minutes=1),
            num_interactions=1,
        )
        sub_session.files = [
            _make_interaction_file(
                created_ms=int((start + timedelta(minutes=1)).timestamp() * 1000),
                completed_ms=int((end - timedelta(minutes=1)).timestamp() * 1000),
                input_tok=300,
                output_tok=150,
                cache_read=50,
                cache_write=25,
            ),
        ]

        workflow = SessionWorkflow(
            workflow_id="test-workflow",
            main_session=main_session,
            sub_agent_sessions=[sub_session],
        )

        metrics = extract_workflow_metrics(workflow, {}, datetime.now())

        # Should aggregate: main (1000+500+200+100=1800) + sub (300+150+50+25=525) = 2325
        assert metrics["tokens.input"] == 1300  # 1000 + 300
        assert metrics["tokens.output"] == 650  # 500 + 150
        assert metrics["tokens.cache_read"] == 250  # 200 + 50
        assert metrics["tokens.cache_write"] == 125  # 100 + 25
        assert metrics["tokens.total"] == 2325

    def test_extract_workflow_metrics_session_counts(self):
        """Should correctly report session and sub-agent counts."""
        start = datetime.now() - timedelta(minutes=5)
        end = datetime.now()

        main_session = _make_session_data(start, end, num_interactions=3)
        sub_session1 = _make_session_data(start, end, num_interactions=2)
        sub_session2 = _make_session_data(start, end, num_interactions=2)

        workflow = SessionWorkflow(
            workflow_id="test-workflow",
            main_session=main_session,
            sub_agent_sessions=[sub_session1, sub_session2],
        )

        metrics = extract_workflow_metrics(workflow, {}, datetime.now())

        assert metrics["session_count"] == 3  # 1 main + 2 sub
        assert metrics["sub_agent_count"] == 2