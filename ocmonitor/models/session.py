"""Session data models for OpenCode Monitor."""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pathlib import Path
from decimal import Decimal
from pydantic import BaseModel, Field, computed_field, field_validator, ConfigDict


class TokenUsage(BaseModel):
    """Model for token usage data."""
    input: int = Field(default=0, ge=0)
    output: int = Field(default=0, ge=0)
    cache_write: int = Field(default=0, ge=0)
    cache_read: int = Field(default=0, ge=0)

    @computed_field
    @property
    def total(self) -> int:
        """Calculate total tokens."""
        return self.input + self.output + self.cache_write + self.cache_read


class TimeData(BaseModel):
    """Model for timing information."""
    created: Optional[int] = Field(default=None, description="Creation timestamp in milliseconds")
    completed: Optional[int] = Field(default=None, description="Completion timestamp in milliseconds")

    @computed_field
    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate duration in milliseconds."""
        if self.created is not None and self.completed is not None:
            return self.completed - self.created
        return None

    @computed_field
    @property
    def created_datetime(self) -> Optional[datetime]:
        """Get creation time as datetime object."""
        if self.created is not None:
            return datetime.fromtimestamp(self.created / 1000)
        return None

    @computed_field
    @property
    def completed_datetime(self) -> Optional[datetime]:
        """Get completion time as datetime object."""
        if self.completed is not None:
            return datetime.fromtimestamp(self.completed / 1000)
        return None


class InteractionFile(BaseModel):
    """Model for a single OpenCode interaction file."""
    file_path: Path
    session_id: str
    model_id: str = Field(default="unknown")
    provider_id: Optional[str] = Field(default=None, description="Provider ID from OpenCode (e.g. github-copilot, genai-nexus)")
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    time_data: Optional[TimeData] = Field(default=None)
    project_path: Optional[str] = Field(default=None, description="Project working directory from OpenCode")
    agent: Optional[str] = Field(default=None, description="Agent type (explore, plan, build, etc.)")
    finish_reason: Optional[str] = Field(default=None, description="Finish reason (stop, tool-calls, etc.)")
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v):
        """Ensure file path is a Path object."""
        return Path(v) if not isinstance(v, Path) else v

    @computed_field
    @property
    def file_name(self) -> str:
        """Get the file name."""
        return self.file_path.name

    @computed_field
    @property
    def display_model(self) -> str:
        """Get the display model string combining provider and model ID.

        Returns 'provider_id/model_id' when provider is known, else just 'model_id'.
        """
        if self.provider_id:
            return f"{self.provider_id}/{self.model_id}"
        return self.model_id

    @computed_field
    @property
    def modification_time(self) -> datetime:
        """Get file modification time."""
        return datetime.fromtimestamp(self.file_path.stat().st_mtime)

    @computed_field
    @property
    def project_name(self) -> str:
        """Get project name from project path."""
        if not self.project_path:
            return "Unknown"
        return Path(self.project_path).name if self.project_path else "Unknown"

    @property
    def is_rate_eligible(self) -> bool:
        """Whether this interaction should be included in output rate calculations.
        Excludes tool-call-only interactions with low output tokens."""
        if self.finish_reason == "tool-calls" and self.tokens.output < 100:
            return False
        return (self.tokens.output > 0
                and self.time_data is not None
                and self.time_data.duration_ms is not None
                and self.time_data.duration_ms > 0)

    def _calculate_cost_from_tokens(self, pricing_data: Dict[str, Any]) -> Decimal:
        """Calculate cost from token usage using pricing data.

        Delegates provider-aware lookup fallback logic to
        FileProcessor.lookup_pricing.

        Args:
            pricing_data: Dictionary of model pricing information

        Returns:
            Calculated cost in USD
        """
        from ..utils.file_utils import FileProcessor
        pricing = FileProcessor.lookup_pricing(
            pricing_data,
            model_id=self.model_id,
            provider_id=self.provider_id,
        )

        if pricing is None:
            return Decimal('0.0')

        cost = Decimal('0.0')

        # Convert to cost per million tokens
        million = Decimal('1000000')

        cost += (Decimal(self.tokens.input) / million) * Decimal(str(pricing.input))
        cost += (Decimal(self.tokens.output) / million) * Decimal(str(pricing.output))
        cost += (Decimal(self.tokens.cache_write) / million) * Decimal(str(pricing.cache_write))
        cost += (Decimal(self.tokens.cache_read) / million) * Decimal(str(pricing.cache_read))

        return cost

    def calculate_cost(self, pricing_data: Dict[str, Any], force_recalculate: bool = False) -> Decimal:
        """Calculate cost for this interaction with flexible model name matching.

        Uses OpenCode's stored cost when available unless force_recalculate is True.
        Falls back to local pricing calculation when stored cost is not available.

        Args:
            pricing_data: Dictionary of model pricing information
            force_recalculate: If True, ignore stored cost and recalculate from pricing data

        Returns:
            Calculated cost in USD
        """
        if not force_recalculate:
            stored_cost = self.raw_data.get('cost')
            if stored_cost is not None and stored_cost > 0:
                return Decimal(str(stored_cost))

        return self._calculate_cost_from_tokens(pricing_data)


class SessionData(BaseModel):
    """Model for a complete OpenCode session."""
    session_id: str
    session_path: Optional[Path] = Field(default=None, description="Path to session directory (None for SQLite sessions)")
    parent_id: Optional[str] = Field(default=None, description="Parent session ID for sub-agents")
    is_sub_agent: bool = Field(default=False, description="Whether this is a sub-agent session")
    files: List[InteractionFile] = Field(default_factory=list)
    session_title: Optional[str] = Field(default=None, description="Human-readable session title from OpenCode")
    agent: Optional[str] = Field(default=None, description="Agent type for this session (from first interaction)")
    source: Literal["sqlite", "files"] = Field(default="sqlite", description="Data source: sqlite or files")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('session_path')
    @classmethod
    def validate_session_path(cls, v):
        """Ensure session path is a Path object if provided."""
        if v is None:
            return None
        return Path(v) if not isinstance(v, Path) else v

    @computed_field
    @property
    def models_used(self) -> List[str]:
        """Get list of unique models used in this session.

        Returns 'provider_id/model_id' when provider is known, else just 'model_id'.
        """
        return list(set(file.display_model for file in self.files))

    @computed_field
    @property
    def total_tokens(self) -> TokenUsage:
        """Calculate total token usage for the session."""
        total = TokenUsage()
        for file in self.files:
            total.input += file.tokens.input
            total.output += file.tokens.output
            total.cache_write += file.tokens.cache_write
            total.cache_read += file.tokens.cache_read
        return total

    @computed_field
    @property
    def start_time(self) -> Optional[datetime]:
        """Get session start time (earliest file creation time)."""
        times = [file.time_data.created_datetime for file in self.files
                if file.time_data and file.time_data.created_datetime]
        return min(times) if times else None

    @computed_field
    @property
    def end_time(self) -> Optional[datetime]:
        """Get session end time (latest file completion time)."""
        times = [file.time_data.completed_datetime for file in self.files
                if file.time_data and file.time_data.completed_datetime]
        return max(times) if times else None

    @computed_field
    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate total session duration in milliseconds."""
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time).total_seconds() * 1000)
        return None

    @computed_field
    @property
    def duration_hours(self) -> float:
        """Calculate session duration in hours."""
        if self.duration_ms:
            return self.duration_ms / (1000 * 60 * 60)
        return 0.0

    @computed_field
    @property
    def duration_percentage(self) -> float:
        """Calculate session duration as percentage of the 5-hour quota.

        Not capped: values above 100 mean the session ran over quota.
        """
        max_hours = 5.0
        return (self.duration_hours / max_hours) * 100.0

    @computed_field
    @property
    def total_processing_time_ms(self) -> int:
        """Calculate total processing time across all files."""
        total = 0
        for file in self.files:
            if file.time_data and file.time_data.duration_ms:
                total += file.time_data.duration_ms
        return total

    def calculate_total_cost(self, pricing_data: Dict[str, Any], force_recalculate: bool = False) -> Decimal:
        """Calculate total cost for the session.

        Args:
            pricing_data: Dictionary of model pricing information
            force_recalculate: If True, ignore stored costs and recalculate from pricing data
        """
        costs = [file.calculate_cost(pricing_data, force_recalculate) for file in self.files]
        return Decimal(sum(costs))

    def get_model_breakdown(self, pricing_data: Dict[str, Any], force_recalculate: bool = False) -> Dict[str, Dict[str, Any]]:
        """Get breakdown of usage and cost by model.

        Args:
            pricing_data: Dictionary of model pricing information
            force_recalculate: If True, ignore stored costs and recalculate from pricing data
        """
        breakdown = {}

        for display_model in self.models_used:
            model_files = [f for f in self.files if f.display_model == display_model]
            model_tokens = TokenUsage()
            model_cost = Decimal('0.0')
            model_duration_ms = 0
            interaction_rates: list[float] = []

            for file in model_files:
                model_tokens.input += file.tokens.input
                model_tokens.output += file.tokens.output
                model_tokens.cache_write += file.tokens.cache_write
                model_tokens.cache_read += file.tokens.cache_read
                model_cost += file.calculate_cost(pricing_data, force_recalculate)
                if file.time_data and file.time_data.duration_ms:
                    model_duration_ms += file.time_data.duration_ms
                if file.is_rate_eligible:
                    rate = file.tokens.output / (file.time_data.duration_ms / 1000)
                    interaction_rates.append(rate)

            breakdown[display_model] = {
                'files': len(model_files),
                'tokens': model_tokens,
                'cost': model_cost,
                'duration_ms': model_duration_ms,
                'interaction_rates': interaction_rates,
            }

        return breakdown

    @computed_field
    @property
    def interaction_count(self) -> int:
        """Get number of interactions (files) in this session."""
        return len(self.files)
    
    @property
    def non_zero_token_files(self) -> List[InteractionFile]:
        """Get files with non-zero token usage."""
        return [file for file in self.files if file.tokens.total > 0]

    @computed_field
    @property
    def project_name(self) -> str:
        """Get project name for this session based on most common project path."""
        if not self.files:
            return "Unknown"
        
        # Get project paths from files that have them
        project_paths = [f.project_path for f in self.files if f.project_path]
        
        if not project_paths:
            return "Unknown"
        
        # Use the most common project path (in case there are mixed paths)
        from collections import Counter
        most_common_path = Counter(project_paths).most_common(1)[0][0]
        
        return Path(most_common_path).name if most_common_path else "Unknown"

    @computed_field
    @property
    def display_title(self) -> str:
        """Get display-friendly session title, with fallback to session ID."""
        if self.session_title:
            # Truncate long titles for better display
            if len(self.session_title) > 50:
                return self.session_title[:47] + "..."
            return self.session_title
        
        # Fallback to session ID
        return self.session_id
