"""Configuration management for OpenCode Monitor."""

import json
import os
import warnings
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

import toml
from pydantic import BaseModel, Field, field_validator


def opencode_storage_path(path: Optional[str] = None) -> str:
    base = os.getenv("XDG_DATA_HOME") or "~/.local/share"
    parts = [base, "opencode", "storage"]
    if path:
        parts.append(path)
    return os.path.join(*parts)


def get_default_cache_path() -> str:
    """Get default cache path for models.dev API."""
    cache_home = os.getenv("XDG_CACHE_HOME") or "~/.cache"
    return os.path.join(cache_home, "ocmonitor", "models_dev_api.json")


def _default_rates_cache_path() -> str:
    """Get default cache path for exchange rates."""
    cache_home = os.getenv("XDG_CACHE_HOME") or "~/.cache"
    return os.path.join(cache_home, "ocmonitor", "exchange_rates.json")


class PathsConfig(BaseModel):
    """Configuration for file paths."""
    messages_dir: str = Field(default=opencode_storage_path("message"))
    opencode_storage_dir: str = Field(default=opencode_storage_path())
    database_file: str = Field(default="~/.local/share/opencode/opencode.db")
    export_dir: str = Field(default="./exports")

    @field_validator('messages_dir', 'opencode_storage_dir', 'database_file', 'export_dir')
    @classmethod
    def expand_path(cls, v):
        """Expand user paths and environment variables."""
        return os.path.expanduser(os.path.expandvars(v))


class UIConfig(BaseModel):
    """Configuration for UI appearance."""
    table_style: str = Field(default="rich", pattern="^(rich|simple|minimal)$")
    theme: str = Field(default="dark", pattern="^(light|dark)$")
    progress_bars: bool = Field(default=True)
    colors: bool = Field(default=True)
    live_refresh_interval: int = Field(default=1, ge=1, le=60)


class ExportConfig(BaseModel):
    """Configuration for data export."""
    default_format: str = Field(default="csv", pattern="^(csv|json)$")
    include_metadata: bool = Field(default=True)
    include_raw_data: bool = Field(default=False)


class ModelsConfig(BaseModel):
    """Configuration for model pricing."""
    config_file: str = Field(default="models.json")
    # Remote pricing fallback settings
    remote_fallback: bool = Field(default=False)
    remote_url: str = Field(default="https://models.dev/api.json")
    remote_timeout_seconds: int = Field(default=8, ge=1, le=60)
    remote_cache_ttl_hours: int = Field(default=24, ge=1, le=168)
    remote_cache_path: str = Field(default=get_default_cache_path())
    user_file: Optional[str] = Field(default="~/.config/ocmonitor/models.json")
    allow_stale_cache_on_error: bool = Field(default=True)

    @field_validator('remote_cache_path', 'user_file')
    @classmethod
    def expand_model_paths(cls, v):
        """Expand user paths and environment variables for model paths."""
        if v is None:
            return v
        return os.path.expanduser(os.path.expandvars(v))


class AnalyticsConfig(BaseModel):
    """Configuration for analytics."""
    default_timeframe: str = Field(default="daily", pattern="^(daily|weekly|monthly)$")
    recent_sessions_limit: int = Field(default=50, ge=1, le=1000)


class MetricsConfig(BaseModel):
    """Configuration for Prometheus metrics server."""
    port: int = Field(default=9090, ge=1024, le=65535)
    host: str = Field(default="0.0.0.0")


class CurrencyConfig(BaseModel):
    """Configuration for currency display and conversion."""
    code: str = Field(default="USD")
    symbol: str = Field(default="$")
    rate: Decimal = Field(default=Decimal("1.0"), ge=0)
    display_format: str = Field(default="symbol_prefix", pattern="^(symbol_prefix|code_suffix)$")
    decimals: Optional[int] = Field(default=None, ge=0, le=6)
    # Remote rate fetching
    remote_rates: bool = Field(default=False)
    remote_rates_url: str = Field(default="https://api.frankfurter.dev/v1/latest?base=USD")
    remote_rates_timeout_seconds: int = Field(default=8, ge=1, le=60)
    remote_rates_cache_ttl_hours: int = Field(default=24, ge=1, le=168)
    remote_rates_cache_path: str = Field(default_factory=lambda: _default_rates_cache_path())
    allow_stale_rates_on_error: bool = Field(default=True)

    @field_validator('remote_rates_cache_path')
    @classmethod
    def expand_currency_paths(cls, v):
        if v is None:
            return v
        return os.path.expanduser(os.path.expandvars(v))


class Config(BaseModel):
    """Main configuration class."""
    paths: PathsConfig = Field(default_factory=PathsConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    currency: CurrencyConfig = Field(default_factory=CurrencyConfig)


class ModelPricing(BaseModel):
    """Model for pricing information."""
    input: Decimal = Field(description="Cost per 1M input tokens")
    output: Decimal = Field(description="Cost per 1M output tokens")
    cache_write: Decimal = Field(alias="cacheWrite", description="Cost per 1M cache write tokens")
    cache_read: Decimal = Field(alias="cacheRead", description="Cost per 1M cache read tokens")
    context_window: int = Field(alias="contextWindow", description="Maximum context window size")
    session_quota: Decimal = Field(alias="sessionQuota", description="Maximum session cost quota")


def merge_model_prices(
    local_raw: Dict[str, Any],
    user_raw: Dict[str, Any],
    remote_raw: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge pricing data from multiple sources with proper precedence.
    
    Precedence (highest to lowest):
    1. User override file (user_raw)
    2. Project/local models.json (local_raw)
    3. models.dev fallback (remote_raw) - fill-only
    
    Args:
        local_raw: Raw pricing dict from local models.json
        user_raw: Raw pricing dict from user override file
        remote_raw: Raw pricing dict from models.dev (fill-only)
        
    Returns:
        Merged raw pricing dict
    """
    merged = {}
    
    # Start with remote data (lowest precedence - fill-only)
    if remote_raw:
        for model_name, model_data in remote_raw.items():
            merged[model_name] = model_data.copy()
    
    # Overlay local data (middle precedence)
    for model_name, model_data in local_raw.items():
        if model_name in merged:
            # Field-level merge: local overwrites remote for existing model
            merged[model_name].update(model_data)
        else:
            merged[model_name] = model_data.copy()
    
    # Overlay user data (highest precedence)
    for model_name, model_data in user_raw.items():
        if model_name in merged:
            # Field-level merge: user overwrites everything for existing model
            merged[model_name].update(model_data)
        else:
            merged[model_name] = model_data.copy()
    
    return merged


class ConfigManager:
    """Manages configuration loading and access."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager.

        Args:
            config_path: Path to configuration file. If None, searches standard locations.
        """
        self.config_path = config_path or self._find_config_file()
        self._config: Optional[Config] = None
        self._pricing_data: Optional[Dict[str, ModelPricing]] = None

    def _find_config_file(self) -> str:
        """Find configuration file in standard locations.
        
        Search order (first found wins):
        1. User config: ~/.config/ocmonitor/config.toml
        2. Project-local config.toml
        3. Project-local ocmonitor.toml
        4. Packaged fallback: ocmonitor/config.toml (always returns this if nothing else exists)
        """
        search_paths = [
            os.path.expanduser("~/.config/ocmonitor/config.toml"),
            "config.toml",
            "ocmonitor.toml",
            os.path.join(os.path.dirname(__file__), "config.toml"),
        ]

        for path in search_paths:
            if os.path.exists(path):
                return path

        # Return default path even if it doesn't exist
        return search_paths[-1]

    @property
    def config(self) -> Config:
        """Get configuration, loading if necessary."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _load_config(self) -> Config:
        """Load configuration from TOML file."""
        if not os.path.exists(self.config_path):
            # Return default configuration if file doesn't exist
            return Config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = toml.load(f)
            return Config(**config_data)
        except (toml.TomlDecodeError, ValueError) as e:
            raise ValueError(f"Invalid configuration file {self.config_path}: {e}")

    def load_pricing_data(self, no_remote: bool = False) -> Dict[str, ModelPricing]:
        """Load model pricing data.
        
        Args:
            no_remote: If True, disable remote fallback regardless of config setting
            
        Returns:
            Dict mapping model names to ModelPricing objects
        """
        if self._pricing_data is None:
            self._pricing_data = self._load_pricing_data(no_remote=no_remote)
        return self._pricing_data

    def _load_pricing_data(self, no_remote: bool = False) -> Dict[str, ModelPricing]:
        """Load pricing data from all sources and merge them.
        
        Args:
            no_remote: If True, disable remote fallback regardless of config setting
            
        Returns:
            Dict mapping model names to ModelPricing objects
        """
        models_config = self.config.models
        
        # Load local project pricing file (with package fallback for default models)
        local_raw = self._load_raw_pricing_file(models_config.config_file, use_package_fallback=True)
        
        # Load user override file if it exists
        user_raw = {}
        if models_config.user_file:
            user_path = Path(models_config.user_file)
            if user_path.exists():
                user_raw = self._load_raw_pricing_file(str(user_path))
        
        # Load remote pricing if enabled and not disabled by CLI flag
        remote_raw = {}
        if not no_remote and models_config.remote_fallback:
            try:
                from .services.price_fetcher import get_remote_payload, map_models_dev_to_local
                
                cache_path = Path(models_config.remote_cache_path)
                payload = get_remote_payload(
                    url=models_config.remote_url,
                    timeout=models_config.remote_timeout_seconds,
                    cache_path=cache_path,
                    cache_ttl_hours=models_config.remote_cache_ttl_hours,
                    allow_stale_on_error=models_config.allow_stale_cache_on_error,
                )
                
                if payload is not None:
                    remote_raw = map_models_dev_to_local(payload)
            except Exception:
                # Remote fetch failed, continue with local-only pricing
                # Don't fail the entire operation due to remote issues
                pass
        
        # Merge all sources
        merged_raw = merge_model_prices(local_raw, user_raw, remote_raw)
        
        # Validate each merged entry into ModelPricing objects
        pricing_data = {}
        for model_name, model_data in merged_raw.items():
            try:
                pricing_data[model_name] = ModelPricing(**model_data)
            except (ValueError, TypeError) as e:
                # Skip invalid entries with warning
                warnings.warn(
                    f"Skipping invalid pricing data for model '{model_name}': {e}",
                    UserWarning,
                    stacklevel=2,
                )
                continue
        
        return pricing_data

    def _load_raw_pricing_file(self, file_path: str, use_package_fallback: bool = False) -> Dict[str, Any]:
        """Load raw pricing data from a JSON file.
        
        Args:
            file_path: Path to pricing JSON file (can be relative to config)
            use_package_fallback: If True and file not found, try package directory
            
        Returns:
            Raw dict of pricing data
        """
        original_path = file_path
        
        # Try relative to config file first
        if not os.path.isabs(file_path):
            config_dir = os.path.dirname(self.config_path)
            abs_path = os.path.join(config_dir, file_path)
            if os.path.exists(abs_path):
                file_path = abs_path
            else:
                # Try in same directory as this module
                module_path = os.path.join(os.path.dirname(__file__), file_path)
                if os.path.exists(module_path):
                    file_path = module_path
        
        # For the main models file, fall back to package directory
        if use_package_fallback and not os.path.exists(file_path):
            package_models = os.path.join(os.path.dirname(__file__), "models.json")
            if os.path.exists(package_models):
                file_path = package_models
        
        if not os.path.exists(file_path):
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def get_model_pricing(self, model_name: str, no_remote: bool = False) -> Optional[ModelPricing]:
        """Get pricing information for a specific model.
        
        Args:
            model_name: Name of the model to look up
            no_remote: If True, disable remote fallback
            
        Returns:
            ModelPricing object or None if not found
        """
        pricing_data = self.load_pricing_data(no_remote=no_remote)
        return pricing_data.get(model_name)

    def reload(self):
        """Reload configuration and pricing data."""
        self._config = None
        self._pricing_data = None


# Global configuration manager instance
config_manager = ConfigManager()
