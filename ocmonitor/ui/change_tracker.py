"""Change tracking utilities for monitoring value changes."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional, Set, Union

from ..models.session import SessionData
from ..models.workflow import SessionWorkflow

if TYPE_CHECKING:
    from ..services.live_monitor import WorkflowWrapper


class ValueChangeTracker:
    """Track changes in metrics data over time."""

    def __init__(self) -> None:
        self._prev_data: Optional[Dict[str, Any]] = None

    def update_and_diff(self, current_data: Dict[str, Any]) -> Set[str]:
        """Compare current data with previous, return set of changed field names.

        First call returns empty set (no previous data to compare against).

        Args:
            current_data: Dictionary of current metric values

        Returns:
            Set of field names that changed since last update
        """
        if self._prev_data is None:
            self._prev_data = dict(current_data)  # defensive copy
            return set()
        changed = self._diff(self._prev_data, current_data)
        self._prev_data = dict(current_data)
        return changed

    def _diff(self, prev: Dict[str, Any], current: Dict[str, Any]) -> Set[str]:
        """Compute set of fields that differ between two dictionaries."""
        changed_fields: Set[str] = set()
        for key, value in current.items():
            if key not in prev or prev[key] != value:
                changed_fields.add(key)
        return changed_fields

    def reset(self) -> None:
        """Reset tracker (e.g., on workflow switch)."""
        self._prev_data = None


def extract_session_metrics(
    session: SessionData,
    pricing_data: Dict[str, Any],
    current_time: datetime,
) -> Dict[str, Any]:
    """Extract key metrics from a session for change tracking.

    Args:
        session: SessionData instance to extract metrics from
        pricing_data: Dictionary of model pricing information
        current_time: Current timestamp for duration calculation

    Returns:
        Dictionary containing session metrics
    """
    tokens = session.total_tokens
    metrics: Dict[str, Any] = {
        "tokens.input": tokens.input,
        "tokens.output": tokens.output,
        "tokens.cache_read": tokens.cache_read,
        "tokens.cache_write": tokens.cache_write,
        "tokens.total": tokens.total,
        "interaction_count": session.interaction_count,
    }
    # Cost (may be None if no pricing)
    try:
        cost = session.calculate_total_cost(pricing_data)
        metrics["cost.total"] = float(cost) if cost else 0.0
    except Exception:
        metrics["cost.total"] = 0.0
    # Duration
    if session.start_time and current_time:
        duration_ms = int((current_time - session.start_time).total_seconds() * 1000)
        metrics["duration_ms"] = duration_ms
    return metrics


def extract_workflow_metrics(
    workflow: Union[SessionWorkflow, "WorkflowWrapper"],
    pricing_data: Dict[str, Any],
    current_time: datetime,
) -> Dict[str, Any]:
    """Extract key metrics from a workflow for change tracking.

    Args:
        workflow: SessionWorkflow or WorkflowWrapper instance
        pricing_data: Dictionary of model pricing information
        current_time: Current timestamp for duration calculation

    Returns:
        Dictionary containing workflow metrics, including per-model tokens/cost
    """
    tokens = workflow.total_tokens
    metrics: Dict[str, Any] = {
        "tokens.input": tokens.input,
        "tokens.output": tokens.output,
        "tokens.cache_read": tokens.cache_read,
        "tokens.cache_write": tokens.cache_write,
        "tokens.total": tokens.total,
        "session_count": workflow.session_count,
        "sub_agent_count": workflow.sub_agent_count,
    }
    # Cost
    try:
        cost = workflow.calculate_total_cost(pricing_data)
        metrics["cost.total"] = float(cost) if cost else 0.0
    except Exception:
        metrics["cost.total"] = 0.0
    # Duration
    if workflow.start_time and current_time:
        duration_ms = int((current_time - workflow.start_time).total_seconds() * 1000)
        metrics["duration_ms"] = duration_ms
    
    # Per-model tokens and cost for model panel highlighting
    # Aggregate across all sessions (same logic as create_workflow_model_panel)
    try:
        from collections import defaultdict
        model_totals: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"tokens": 0, "cost": Decimal("0.0")}
        )
        for session in workflow.all_sessions:
            model_breakdown = session.get_model_breakdown(pricing_data)
            for model, stats in model_breakdown.items():
                model_totals[model]["tokens"] += stats["tokens"].total
                model_totals[model]["cost"] += stats["cost"]
        
        for model, totals in model_totals.items():
            model_key = f"model.{model}"
            metrics[f"{model_key}.tokens"] = totals["tokens"]
            metrics[f"{model_key}.cost"] = float(totals["cost"])
    except Exception:
        pass  # Model breakdown is optional
    
    return metrics