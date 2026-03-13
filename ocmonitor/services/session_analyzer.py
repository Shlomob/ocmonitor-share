"""Session analysis service for OpenCode Monitor."""

import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from decimal import Decimal

from ..models.session import SessionData, InteractionFile, TokenUsage
from ..models.analytics import (
    DailyUsage, WeeklyUsage, MonthlyUsage, ModelUsageStats,
    ModelBreakdownReport, ModelDetailStats, ProjectBreakdownReport, TimeframeAnalyzer
)
from ..utils.file_utils import FileProcessor
from ..utils.data_loader import DataLoader, DataSourceError
from ..utils.time_utils import TimeUtils
from ..config import ModelPricing


class SessionAnalyzer:
    """Service for analyzing OpenCode sessions."""

    def __init__(self, pricing_data: Dict[str, ModelPricing]):
        """Initialize session analyzer.

        Args:
            pricing_data: Model pricing information
        """
        self.pricing_data = pricing_data
        self._data_loader = DataLoader()

    def load_session_hierarchy(self, base_path: Optional[str] = None) -> Dict[str, Any]:
        """Load sessions organized by parent-child hierarchy.
        
        Uses the DataLoader which prefers SQLite but falls back to files.
        
        Args:
            base_path: Optional path override (used only for file-based loading)
            
        Returns:
            Dictionary with:
                - 'root_sessions': List of parent sessions with sub_agents
                - 'all_sessions': Flat list of all sessions
                - 'source': 'sqlite' or 'files'
                
        Raises:
            DataSourceError: If no data source is available
        """
        return self._data_loader.load_session_hierarchy()

    def analyze_all_sessions(self, base_path: Optional[str] = None, limit: Optional[int] = None) -> List[SessionData]:
        """Analyze all sessions from the preferred data source.
        
        Uses the DataLoader which prefers SQLite but falls back to files.
        
        Args:
            base_path: Optional path override (used only for file-based loading)
            limit: Maximum number of sessions to analyze
            
        Returns:
            List of SessionData objects
        """
        return self._data_loader.load_all_sessions(limit)

    def get_data_source_info(self) -> Dict[str, Any]:
        """Get information about the current data source.
        
        Returns:
            Dictionary with source availability and paths
        """
        return self._data_loader.get_source_info()

    def analyze_single_session(self, session_path: str) -> Optional[SessionData]:
        """Analyze a single session directory.

        Args:
            session_path: Path to session directory

        Returns:
            SessionData object or None if analysis failed
        """
        path = Path(session_path)
        return FileProcessor.load_session_data(path)

    def get_sessions_summary(self, sessions: List[SessionData]) -> Dict[str, Any]:
        """Generate summary statistics for multiple sessions.

        Args:
            sessions: List of sessions to summarize

        Returns:
            Dictionary with summary statistics
        """
        if not sessions:
            return {
                'total_sessions': 0,
                'total_interactions': 0,
                'total_tokens': TokenUsage(),
                'total_cost': Decimal('0.0'),
                'models_used': [],
                'date_range': 'No sessions'
            }

        total_tokens = TokenUsage()
        total_cost = Decimal('0.0')
        total_interactions = 0
        models_used = set()
        start_times = []
        end_times = []

        for session in sessions:
            session_tokens = session.total_tokens
            total_tokens.input += session_tokens.input
            total_tokens.output += session_tokens.output
            total_tokens.cache_write += session_tokens.cache_write
            total_tokens.cache_read += session_tokens.cache_read

            total_cost += session.calculate_total_cost(self.pricing_data)
            total_interactions += session.interaction_count
            models_used.update(session.models_used)

            if session.start_time:
                start_times.append(session.start_time)
            if session.end_time:
                end_times.append(session.end_time)

        # Calculate date range
        date_range = 'Unknown'
        if start_times and end_times:
            earliest = min(start_times)
            latest = max(end_times)
            if earliest.date() == latest.date():
                date_range = earliest.strftime('%Y-%m-%d')
            else:
                date_range = f"{earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')}"

        return {
            'total_sessions': len(sessions),
            'total_interactions': total_interactions,
            'total_tokens': total_tokens,
            'total_cost': total_cost,
            'models_used': sorted(list(models_used)),
            'date_range': date_range,
            'earliest_session': min(start_times) if start_times else None,
            'latest_session': max(end_times) if end_times else None
        }

    def create_daily_breakdown(self, sessions: List[SessionData]) -> List[DailyUsage]:
        """Create daily usage breakdown.

        Args:
            sessions: List of sessions to analyze

        Returns:
            List of DailyUsage objects
        """
        return TimeframeAnalyzer.create_daily_breakdown(sessions)

    def create_weekly_breakdown(self, sessions: List[SessionData], week_start_day: int = 0) -> List[WeeklyUsage]:
        """Create weekly usage breakdown.

        Args:
            sessions: List of sessions to analyze
            week_start_day: Day to start week on (0=Monday, 6=Sunday)

        Returns:
            List of WeeklyUsage objects
        """
        daily_usage = self.create_daily_breakdown(sessions)
        return TimeframeAnalyzer.create_weekly_breakdown(daily_usage, week_start_day)

    def create_monthly_breakdown(self, sessions: List[SessionData]) -> List[MonthlyUsage]:
        """Create monthly usage breakdown.

        Args:
            sessions: List of sessions to analyze

        Returns:
            List of MonthlyUsage objects
        """
        daily_usage = self.create_daily_breakdown(sessions)
        weekly_usage = TimeframeAnalyzer.create_weekly_breakdown(daily_usage)
        return TimeframeAnalyzer.create_monthly_breakdown(weekly_usage)

    def create_model_breakdown(self, sessions: List[SessionData],
                             timeframe: str = "all",
                             start_date: Optional[date] = None,
                             end_date: Optional[date] = None) -> ModelBreakdownReport:
        """Create model usage breakdown.

        Args:
            sessions: List of sessions to analyze
            timeframe: Timeframe for analysis ("all", "daily", "weekly", "monthly")
            start_date: Start date filter
            end_date: End date filter

        Returns:
            ModelBreakdownReport object
        """
        return TimeframeAnalyzer.create_model_breakdown(
            sessions, self.pricing_data, timeframe, start_date, end_date
        )

    def create_project_breakdown(self, sessions: List[SessionData],
                               timeframe: str = "all",
                               start_date: Optional[date] = None,
                               end_date: Optional[date] = None) -> ProjectBreakdownReport:
        """Create project usage breakdown.

        Args:
            sessions: List of sessions to analyze
            timeframe: Timeframe for analysis ("all", "daily", "weekly", "monthly")
            start_date: Start date filter
            end_date: End date filter

        Returns:
            ProjectBreakdownReport object
        """
        return TimeframeAnalyzer.create_project_breakdown(
            sessions, self.pricing_data, timeframe, start_date, end_date
        )

    def filter_sessions_by_date(self, sessions: List[SessionData],
                               start_date: Optional[date] = None,
                               end_date: Optional[date] = None) -> List[SessionData]:
        """Filter sessions by date range.

        Args:
            sessions: List of sessions to filter
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Filtered list of sessions
        """
        if not start_date and not end_date:
            return sessions

        filtered = []
        for session in sessions:
            # Check if session has any activity in the date range
            session_start_date = (
                session.start_time.date() if session.start_time else None
            )
            session_end_date = (
                session.end_time.date() if session.end_time else session_start_date
            )

            if session_start_date:
                # Include if: started in range OR ended in range OR spans the range
                in_range = False

                # Check if start date is in range
                if TimeUtils.date_in_range(session_start_date, start_date, end_date):
                    in_range = True
                # Check if end date is in range
                elif session_end_date and TimeUtils.date_in_range(
                    session_end_date, start_date, end_date
                ):
                    in_range = True
                # Check if session spans the range (started before, ended after)
                elif session_end_date and start_date and end_date:
                    if session_start_date < start_date and session_end_date > end_date:
                        in_range = True

                if in_range:
                    filtered.append(session)

        return filtered

    def filter_sessions_by_model(self, sessions: List[SessionData], models: List[str]) -> List[SessionData]:
        """Filter sessions by models used.

        Args:
            sessions: List of sessions to filter
            models: List of model names to include

        Returns:
            Filtered list of sessions
        """
        if not models:
            return sessions

        filtered = []
        for session in sessions:
            if any(model in session.models_used for model in models):
                filtered.append(session)

        return filtered

    def get_most_recent_session(self, base_path: str) -> Optional[SessionData]:
        """Get the most recently modified session.

        Args:
            base_path: Path to search for sessions

        Returns:
            Most recent SessionData or None
        """
        return FileProcessor.get_most_recent_session(base_path)

    def get_session_statistics(self, session: SessionData) -> Dict[str, Any]:
        """Get detailed statistics for a single session.

        Args:
            session: Session to analyze

        Returns:
            Dictionary with detailed statistics
        """
        model_breakdown = session.get_model_breakdown(self.pricing_data)
        session_tokens = session.total_tokens
        total_cost = session.calculate_total_cost(self.pricing_data)

        # Calculate averages
        avg_tokens_per_interaction = session_tokens.total // session.interaction_count if session.interaction_count > 0 else 0
        avg_cost_per_interaction = total_cost / session.interaction_count if session.interaction_count > 0 else Decimal('0.0')

        # Time analysis
        time_stats = {}
        if session.start_time and session.end_time:
            time_stats = {
                'start_time': session.start_time,
                'end_time': session.end_time,
                'duration_ms': session.duration_ms,
                'total_processing_time_ms': session.total_processing_time_ms,
                'avg_processing_time_ms': session.total_processing_time_ms // session.interaction_count if session.interaction_count > 0 else 0
            }

        return {
            'session_id': session.session_id,
            'interaction_count': session.interaction_count,
            'models_used': session.models_used,
            'total_tokens': session_tokens,
            'total_cost': total_cost,
            'model_breakdown': model_breakdown,
            'averages': {
                'tokens_per_interaction': avg_tokens_per_interaction,
                'cost_per_interaction': avg_cost_per_interaction
            },
            'time_analysis': time_stats
        }

    def calculate_burn_rate(self, session_path: str, timeframe_minutes: int = 5) -> float:
        """Calculate token burn rate for a session.

        Args:
            session_path: Path to session directory
            timeframe_minutes: Timeframe in minutes for burn rate calculation

        Returns:
            Tokens per minute over the timeframe
        """
        path = Path(session_path)
        if not path.exists():
            return 0.0

        json_files = FileProcessor.find_json_files(path)
        if not json_files:
            return 0.0

        # Get current time and timeframe
        now = time.time()
        timeframe_seconds = timeframe_minutes * 60

        # Filter files within timeframe
        recent_files = []
        for json_file in json_files:
            mod_time = json_file.stat().st_mtime
            if (now - mod_time) <= timeframe_seconds:
                recent_files.append((json_file, mod_time))

        if not recent_files:
            return 0.0

        # Calculate total tokens in recent files
        total_tokens = 0
        for json_file, _ in recent_files:
            interaction = FileProcessor.parse_interaction_file(json_file, path.name)
            if interaction:
                total_tokens += interaction.tokens.total

        # Calculate time span
        if len(recent_files) > 1:
            oldest_time = min([mod_time for _, mod_time in recent_files])
            time_span_minutes = (now - oldest_time) / 60
            if time_span_minutes > 0:
                return total_tokens / time_span_minutes

        return 0.0

    def validate_session_health(self, session: SessionData) -> Dict[str, Any]:
        """Validate session health and identify potential issues.

        Args:
            session: Session to validate

        Returns:
            Dictionary with health check results
        """
        issues = []
        warnings = []

        # Check for empty interactions
        empty_interactions = sum(1 for file in session.files if file.tokens.total == 0)
        if empty_interactions > 0:
            warnings.append(f"{empty_interactions} interactions have no token usage")

        # Check for missing time data
        missing_time = sum(1 for file in session.files if file.time_data is None)
        if missing_time > 0:
            warnings.append(f"{missing_time} interactions missing time data")

        # Check for unknown models
        unknown_models = [model for model in session.models_used if model not in self.pricing_data and model != 'unknown']
        if unknown_models:
            warnings.append(f"Unknown models with no pricing: {', '.join(unknown_models)}")

        # Check for very high costs
        total_cost = session.calculate_total_cost(self.pricing_data)
        if total_cost > Decimal('50.0'):  # Arbitrary threshold
            warnings.append(f"High session cost: ${total_cost:.2f}")

        # Check for extremely long interactions
        long_interactions = []
        for file in session.files:
            if file.time_data and file.time_data.duration_ms and file.time_data.duration_ms > 300000:  # 5 minutes
                long_interactions.append(file.file_name)

        if long_interactions:
            warnings.append(f"Long interactions (>5min): {len(long_interactions)} files")

        return {
            'healthy': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'stats': {
                'total_interactions': session.interaction_count,
                'empty_interactions': empty_interactions,
                'missing_time_data': missing_time,
                'unknown_models': len(unknown_models),
                'total_cost': total_cost
            }
        }

    def find_matching_models(self, query: str) -> List[str]:
        """Find model names matching a query string.

        Args:
            query: Substring to search for in model names

        Returns:
            List of matching model name strings
        """
        return self._data_loader.find_matching_models(query)

    def get_model_detail(self, model_name: str) -> Optional[ModelDetailStats]:
        """Get detailed statistics for a single model.

        Args:
            model_name: Exact model name to query

        Returns:
            ModelDetailStats object or None
        """
        return self._data_loader.get_model_detail(model_name, self.pricing_data)