"""Tests for configuration management."""

import os
import json
import pytest
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch

from ocmonitor.config import (
    PathsConfig,
    UIConfig,
    ExportConfig,
    ModelsConfig,
    AnalyticsConfig,
    MetricsConfig,
    Config,
    ModelPricing,
    ConfigManager,
    opencode_storage_path,
)
import ocmonitor.config as config_module


class TestOpencodeStoragePath:
    """Tests for opencode_storage_path utility function."""
    
    def test_default_path(self):
        """Test default storage path generation."""
        path = opencode_storage_path()
        assert "opencode/storage" in path
        assert "~/.local/share" in path or "XDG_DATA_HOME" in os.environ
    
    def test_path_with_subdirectory(self):
        """Test path generation with subdirectory."""
        path = opencode_storage_path("message")
        assert "opencode/storage/message" in path
    
    def test_xdg_data_home_respected(self, monkeypatch):
        """Test that XDG_DATA_HOME environment variable is respected."""
        monkeypatch.setenv("XDG_DATA_HOME", "/custom/data")
        path = opencode_storage_path()
        assert path.startswith("/custom/data")


class TestPathsConfig:
    """Tests for PathsConfig model."""
    
    def test_default_values(self):
        """Test default path configuration values."""
        config = PathsConfig()
        assert "message" in config.messages_dir
        assert "opencode/storage" in config.opencode_storage_dir
        assert config.export_dir == "./exports"
    
    def test_path_expansion(self):
        """Test that user paths are expanded."""
        config = PathsConfig(messages_dir="~/test/messages")
        assert not config.messages_dir.startswith("~")
        assert config.messages_dir.endswith("test/messages")
    
    def test_environment_variable_expansion(self, monkeypatch):
        """Test that environment variables in paths are expanded."""
        monkeypatch.setenv("TEST_DIR", "/test/path")
        config = PathsConfig(messages_dir="$TEST_DIR/messages")
        assert "/test/path/messages" in config.messages_dir

    def test_database_file_path_expansion(self):
        """Test that database_file user paths are expanded."""
        config = PathsConfig(database_file="~/test/opencode.db")
        assert not config.database_file.startswith("~")
        assert config.database_file.endswith("test/opencode.db")

    def test_database_file_environment_variable_expansion(self, monkeypatch):
        """Test that database_file environment variables are expanded."""
        monkeypatch.setenv("TEST_DB_DIR", "/test/db")
        config = PathsConfig(database_file="$TEST_DB_DIR/opencode.db")
        assert config.database_file == "/test/db/opencode.db"


class TestUIConfig:
    """Tests for UIConfig model."""
    
    def test_default_values(self):
        """Test default UI configuration values."""
        config = UIConfig()
        assert config.table_style == "rich"
        assert config.progress_bars is True
        assert config.colors is True
        assert config.live_refresh_interval == 1
    
    def test_valid_table_styles(self):
        """Test that valid table styles are accepted."""
        for style in ["rich", "simple", "minimal"]:
            config = UIConfig(table_style=style)
            assert config.table_style == style
    
    def test_invalid_table_style(self):
        """Test that invalid table styles are rejected."""
        with pytest.raises(ValueError):
            UIConfig(table_style="invalid")
    
    def test_live_refresh_interval_bounds(self):
        """Test live refresh interval boundary values."""
        # Valid bounds
        config = UIConfig(live_refresh_interval=1)
        assert config.live_refresh_interval == 1
        
        config = UIConfig(live_refresh_interval=60)
        assert config.live_refresh_interval == 60
        
        # Invalid bounds
        with pytest.raises(ValueError):
            UIConfig(live_refresh_interval=0)
        
        with pytest.raises(ValueError):
            UIConfig(live_refresh_interval=61)


class TestExportConfig:
    """Tests for ExportConfig model."""
    
    def test_default_values(self):
        """Test default export configuration values."""
        config = ExportConfig()
        assert config.default_format == "csv"
        assert config.include_metadata is True
        assert config.include_raw_data is False
    
    def test_valid_formats(self):
        """Test that valid export formats are accepted."""
        for fmt in ["csv", "json"]:
            config = ExportConfig(default_format=fmt)
            assert config.default_format == fmt
    
    def test_invalid_format(self):
        """Test that invalid export formats are rejected."""
        with pytest.raises(ValueError):
            ExportConfig(default_format="xml")


class TestAnalyticsConfig:
    """Tests for AnalyticsConfig model."""
    
    def test_default_values(self):
        """Test default analytics configuration values."""
        config = AnalyticsConfig()
        assert config.default_timeframe == "daily"
        assert config.recent_sessions_limit == 50
    
    def test_valid_timeframes(self):
        """Test that valid timeframes are accepted."""
        for tf in ["daily", "weekly", "monthly"]:
            config = AnalyticsConfig(default_timeframe=tf)
            assert config.default_timeframe == tf
    
    def test_recent_sessions_limit_bounds(self):
        """Test recent sessions limit boundary values."""
        # Valid bounds
        config = AnalyticsConfig(recent_sessions_limit=1)
        assert config.recent_sessions_limit == 1
        
        config = AnalyticsConfig(recent_sessions_limit=1000)
        assert config.recent_sessions_limit == 1000
        
        # Invalid bounds
        with pytest.raises(ValueError):
            AnalyticsConfig(recent_sessions_limit=0)
        
        with pytest.raises(ValueError):
            AnalyticsConfig(recent_sessions_limit=1001)


class TestModelPricing:
    """Tests for ModelPricing model."""
    
    def test_pricing_with_aliases(self):
        """Test that pricing data with alias fields is loaded correctly."""
        pricing_data = {
            "input": 3.0,
            "output": 15.0,
            "cacheWrite": 3.75,
            "cacheRead": 0.3,
            "contextWindow": 200000,
            "sessionQuota": 6.0
        }
        
        pricing = ModelPricing(**pricing_data)
        assert pricing.input == Decimal("3.0")
        assert pricing.output == Decimal("15.0")
        assert pricing.cache_write == Decimal("3.75")
        assert pricing.cache_read == Decimal("0.3")
        assert pricing.context_window == 200000
        assert pricing.session_quota == Decimal("6.0")


class TestConfigManager:
    """Tests for ConfigManager class."""
    
    def test_init_without_path(self):
        """Test initialization without explicit config path."""
        manager = ConfigManager()
        # Should find default path
        assert manager.config_path is not None
    
    def test_init_with_path(self, temp_directory):
        """Test initialization with explicit config path."""
        config_path = temp_directory / "test_config.toml"
        config_path.write_text("")
        manager = ConfigManager(config_path=str(config_path))
        assert manager.config_path == str(config_path)
    
    def test_load_default_config(self):
        """Test loading default configuration when file doesn't exist."""
        manager = ConfigManager(config_path="/nonexistent/path/config.toml")
        config = manager.config
        
        assert isinstance(config, Config)
        assert config.ui.table_style == "rich"
        assert config.export.default_format == "csv"
    
    def test_load_config_from_file(self, sample_config_file):
        """Test loading configuration from file."""
        manager = ConfigManager(config_path=str(sample_config_file))
        config = manager.config
        
        assert isinstance(config, Config)
        assert config.ui.table_style == "rich"
        assert config.export.default_format == "csv"
        assert config.analytics.recent_sessions_limit == 50
    
    def test_lazy_loading(self, sample_config_file):
        """Test that configuration is loaded lazily."""
        manager = ConfigManager(config_path=str(sample_config_file))
        assert manager._config is None
        
        # Access config
        _ = manager.config
        assert manager._config is not None
    
    def test_reload_config(self, sample_config_file):
        """Test reloading configuration."""
        manager = ConfigManager(config_path=str(sample_config_file))
        
        # Load config
        config1 = manager.config
        
        # Reload
        manager.reload()
        config2 = manager.config
        
        # Should be new instances
        assert config1 is not config2
    
    def test_load_pricing_data(self, temp_directory):
        """Test loading pricing data from JSON file."""
        # Create config with models.json
        models_data = {
            "test-model": {
                "input": 1.0,
                "output": 2.0,
                "cacheWrite": 1.5,
                "cacheRead": 0.1,
                "contextWindow": 128000,
                "sessionQuota": 5.0
            }
        }
        
        models_file = temp_directory / "models.json"
        models_file.write_text(json.dumps(models_data))
        
        config_file = temp_directory / "config.toml"
        config_file.write_text(f"""
[models]
config_file = "{models_file}"
""")
        
        manager = ConfigManager(config_path=str(config_file))
        pricing = manager.load_pricing_data()
        
        assert "test-model" in pricing
        assert pricing["test-model"].input == Decimal("1.0")
    
    def test_load_pricing_data_missing_file(self, temp_directory):
        """Test loading pricing data when file doesn't exist."""
        config_file = temp_directory / "config.toml"
        config_file.write_text("""
[models]
config_file = "/nonexistent/path/models.json"
""")
        
        manager = ConfigManager(config_path=str(config_file))
        pricing = manager.load_pricing_data()
        
        # Falls back to default models.json in package directory
        assert len(pricing) > 0  # Should have default models
    
    def test_get_model_pricing(self, temp_directory):
        """Test getting pricing for specific model."""
        models_data = {
            "claude-sonnet-4": {
                "input": 3.0,
                "output": 15.0,
                "cacheWrite": 3.75,
                "cacheRead": 0.3,
                "contextWindow": 200000,
                "sessionQuota": 6.0
            }
        }
        
        models_file = temp_directory / "models.json"
        models_file.write_text(json.dumps(models_data))
        
        config_file = temp_directory / "config.toml"
        config_file.write_text(f"""
[models]
config_file = "{models_file}"
""")
        
        manager = ConfigManager(config_path=str(config_file))
        pricing = manager.get_model_pricing("claude-sonnet-4")
        
        assert pricing is not None
        assert pricing.input == Decimal("3.0")
        
        # Test non-existent model
        assert manager.get_model_pricing("non-existent") is None
    
    def test_invalid_config_file(self, temp_directory):
        """Test handling of invalid config file."""
        config_file = temp_directory / "invalid_config.toml"
        config_file.write_text("invalid toml content [[[")
        
        manager = ConfigManager(config_path=str(config_file))
        
        with pytest.raises(ValueError) as exc_info:
            _ = manager.config
        
        assert "Invalid configuration file" in str(exc_info.value)


class TestModelsConfigRemote:
    """Tests for ModelsConfig remote pricing settings."""
    
    def test_models_config_defaults_include_remote_fields(self):
        """Test that ModelsConfig has default remote pricing fields."""
        config = ModelsConfig()
        
        assert hasattr(config, 'remote_fallback')
        assert config.remote_fallback is False
        assert hasattr(config, 'remote_url')
        assert config.remote_url == "https://models.dev/api.json"
        assert hasattr(config, 'remote_timeout_seconds')
        assert config.remote_timeout_seconds == 8
        assert hasattr(config, 'remote_cache_ttl_hours')
        assert config.remote_cache_ttl_hours == 24
        assert hasattr(config, 'remote_cache_path')
        assert ".cache/ocmonitor" in config.remote_cache_path
        assert hasattr(config, 'user_file')
        assert config.user_file == "~/.config/ocmonitor/models.json"
        assert hasattr(config, 'allow_stale_cache_on_error')
        assert config.allow_stale_cache_on_error is True
    
    def test_models_paths_expand_user_and_env_vars(self, monkeypatch):
        """Test that model paths are properly expanded."""
        monkeypatch.setenv("CACHE_DIR", "/custom/cache")
        
        config = ModelsConfig(
            remote_cache_path="$CACHE_DIR/models.json",
            user_file="~/custom/models.json"
        )
        
        assert "/custom/cache/models.json" in config.remote_cache_path
        assert config.user_file is not None
        assert not config.user_file.startswith("~")
        assert config.user_file.endswith("custom/models.json")


class TestMergeModelPrices:
    """Tests for merge_model_prices function."""
    
    def test_merge_precedence_user_over_local_over_remote(self):
        """Test that merge respects precedence: user > local > remote."""
        from ocmonitor.config import merge_model_prices
        
        remote = {"model-a": {"input": 1.0, "output": 10.0}}
        local = {"model-a": {"input": 2.0}, "model-b": {"input": 5.0}}
        user = {"model-a": {"input": 3.0}}
        
        result = merge_model_prices(local, user, remote)
        
        # User value wins for model-a input
        assert result["model-a"]["input"] == 3.0
        # User doesn't have output, local doesn't have output, remote provides it
        assert result["model-a"]["output"] == 10.0
        # Local provides model-b
        assert result["model-b"]["input"] == 5.0
    
    def test_remote_fill_only_does_not_override_local_values(self):
        """Test that remote data only fills gaps, doesn't override."""
        from ocmonitor.config import merge_model_prices
        
        remote = {"model-a": {"input": 1.0, "output": 10.0, "contextWindow": 1000}}
        local = {"model-a": {"input": 2.0}}
        user = {}
        
        result = merge_model_prices(local, user, remote)
        
        # Local input overrides remote
        assert result["model-a"]["input"] == 2.0
        # Remote provides output and contextWindow
        assert result["model-a"]["output"] == 10.0
        assert result["model-a"]["contextWindow"] == 1000
    
    def test_field_level_merge_for_existing_models(self):
        """Test field-level merge when model exists in multiple sources."""
        from ocmonitor.config import merge_model_prices
        
        remote = {"model-x": {"input": 1.0, "output": 10.0, "cacheRead": 0.1}}
        local = {"model-x": {"input": 2.0, "cacheWrite": 5.0}}
        user = {"model-x": {"output": 20.0}}
        
        result = merge_model_prices(local, user, remote)
        
        # User output overrides everything
        assert result["model-x"]["output"] == 20.0
        # Local input overrides remote
        assert result["model-x"]["input"] == 2.0
        # Local cacheWrite is preserved
        assert result["model-x"]["cacheWrite"] == 5.0
        # Remote cacheRead is preserved (not in local or user)
        assert result["model-x"]["cacheRead"] == 0.1


class TestLoadPricingDataWithRemote:
    """Tests for ConfigManager.load_pricing_data with remote fallback."""
    
    def test_user_file_missing_is_non_fatal(self, tmp_path):
        """Test that missing user file doesn't cause errors."""
        # Create minimal local pricing
        models_file = tmp_path / "models.json"
        models_file.write_text(json.dumps({
            "test-model": {
                "input": 1.0, "output": 2.0, "cacheWrite": 1.5,
                "cacheRead": 0.1, "contextWindow": 1000, "sessionQuota": 5.0
            }
        }))
        
        config_file = tmp_path / "config.toml"
        config_file.write_text(f"""
[models]
config_file = "{models_file}"
user_file = "/nonexistent/path/models.json"
remote_fallback = false
""")
        
        manager = ConfigManager(config_path=str(config_file))
        pricing = manager.load_pricing_data()
        
        # Should still load local pricing without error
        assert "test-model" in pricing
    
    def test_load_pricing_data_respects_no_remote_override(self, tmp_path):
        """Test that no_remote=True disables remote fallback."""
        models_file = tmp_path / "models.json"
        models_file.write_text(json.dumps({}))
        
        config_file = tmp_path / "config.toml"
        config_file.write_text(f"""
[models]
config_file = "{models_file}"
remote_fallback = true
""")
        
        manager = ConfigManager(config_path=str(config_file))
        
        # Patch where it's imported, not where it's defined
        with patch('ocmonitor.services.price_fetcher.get_remote_payload') as mock_get:
            mock_get.return_value = {"providers": {}}
            
            # With no_remote=True, should not call get_remote_payload
            pricing = manager.load_pricing_data(no_remote=True)
            mock_get.assert_not_called()
            
            # Reset mock
            mock_get.reset_mock()
            
            # With no_remote=False (default), should call get_remote_payload
            manager._pricing_data = None  # Clear cache
            pricing = manager.load_pricing_data(no_remote=False)
            mock_get.assert_called_once()
    
    def test_invalid_remote_entries_are_skipped_not_fatal(self, tmp_path):
        """Test that invalid pricing entries are skipped with warning."""
        models_file = tmp_path / "models.json"
        models_file.write_text(json.dumps({
            "valid-model": {
                "input": 1.0, "output": 2.0, "cacheWrite": 1.5,
                "cacheRead": 0.1, "contextWindow": 1000, "sessionQuota": 5.0
            },
            "invalid-model": {
                "input": "not-a-number",  # Invalid type
                "output": 2.0
            }
        }))
        
        config_file = tmp_path / "config.toml"
        config_file.write_text(f"""
[models]
config_file = "{models_file}"
remote_fallback = false
""")
        
        manager = ConfigManager(config_path=str(config_file))
        
        with pytest.warns(UserWarning, match="Skipping invalid pricing data"):
            pricing = manager.load_pricing_data()
        
        # Valid model should be present
        assert "valid-model" in pricing
        # Invalid model should be skipped
        assert "invalid-model" not in pricing


class TestMetricsConfig:
    """Tests for MetricsConfig model."""

    def test_metrics_config_defaults(self):
        """Test default metrics configuration values."""
        config = MetricsConfig()
        assert config.port == 9090
        assert config.host == "0.0.0.0"

    def test_metrics_config_in_main_config(self):
        """Test that Config has a metrics attribute."""
        config = Config()
        assert hasattr(config, "metrics")
        assert isinstance(config.metrics, MetricsConfig)
        assert config.metrics.port == 9090

    def test_metrics_config_from_toml(self, temp_directory):
        """Test parsing TOML with [metrics] section."""
        config_file = temp_directory / "config.toml"
        config_file.write_text("""
[metrics]
port = 8080
host = "127.0.0.1"
""")
        manager = ConfigManager(config_path=str(config_file))
        cfg = manager.config
        assert cfg.metrics.port == 8080
        assert cfg.metrics.host == "127.0.0.1"

    def test_metrics_config_port_validation(self):
        """Test port range validation."""
        with pytest.raises(ValueError):
            MetricsConfig(port=80)  # Below 1024
        with pytest.raises(ValueError):
            MetricsConfig(port=70000)  # Above 65535


class TestUtf8ConfigHandling:
    """Regression tests for UTF-8 encoding handling in config files."""

    def test_load_config_with_utf8_currency_symbols_in_comments(self, temp_directory):
        """Test that TOML config files with UTF-8 currency symbols load correctly.

        This is a regression test for Windows where the default encoding (e.g., GBK)
        would cause parsing to fail when the packaged config contains UTF-8 characters.
        """
        config_content = """
# Config with £, €, ¥, ₹ symbols
[currency]
code = "EUR"
symbol = "€"
rate = 0.92
display_format = "symbol_prefix"

# Preset rates:
# GBP: code = "GBP", symbol = "£", rate = 0.79
# EUR: code = "EUR", symbol = "€", rate = 0.92
# CNY: code = "CNY", symbol = "¥", rate = 7.24
# JPY: code = "JPY", symbol = "¥", rate = 149.50
# INR: code = "INR", symbol = "₹", rate = 83.12
"""
        config_path = temp_directory / "utf8_config.toml"
        config_path.write_text(config_content, encoding="utf-8")

        manager = ConfigManager(config_path=str(config_path))
        config = manager.config

        assert config.currency.code == "EUR"
        assert config.currency.symbol == "€"
        assert config.currency.rate == Decimal("0.92")

    def test_load_config_with_utf8_in_values(self, temp_directory):
        """Test that TOML config files with UTF-8 in string values load correctly."""
        config_content = """
[paths]
messages_dir = "~/OpenCode/数据"

[ui]
# Theme name with non-ASCII
table_style = "rich"
"""
        config_path = temp_directory / "utf8_values.toml"
        config_path.write_text(config_content, encoding="utf-8")

        manager = ConfigManager(config_path=str(config_path))
        config = manager.config

        assert "数据" in config.paths.messages_dir

    def test_load_pricing_file_with_utf8_characters(self, temp_directory):
        """Test that JSON pricing files with UTF-8 content load correctly."""
        models_data = {
            "test-model": {
                "input": 1.0,
                "output": 2.0,
                "cacheWrite": 1.5,
                "cacheRead": 0.1,
                "contextWindow": 128000,
                "sessionQuota": 5.0
            }
        }

        models_file = temp_directory / "models.json"
        models_file.write_text(json.dumps(models_data), encoding="utf-8")

        config_file = temp_directory / "config.toml"
        config_file.write_text(f"""
[models]
config_file = "{models_file}"
remote_fallback = false
""")

        manager = ConfigManager(config_path=str(config_file))
        pricing = manager.load_pricing_data()

        assert "test-model" in pricing
        assert pricing["test-model"].input == Decimal("1.0")


class TestConfigSearchPrecedence:
    """Regression tests for config file search precedence."""

    def test_explicit_config_path_overrides_search(self, temp_directory):
        """Test that explicit config_path takes highest priority."""
        explicit_config = temp_directory / "explicit.toml"
        explicit_config.write_text("""
[ui]
table_style = "minimal"
""")

        manager = ConfigManager(config_path=str(explicit_config))
        assert manager.config.ui.table_style == "minimal"

    def test_find_config_file_returns_user_config_when_exists(self, temp_directory, monkeypatch):
        """Test that user config path is checked first in search order."""
        user_config_path = Path(temp_directory) / ".config" / "ocmonitor" / "config.toml"
        user_config_path.parent.mkdir(parents=True, exist_ok=True)
        user_config_path.write_text("""
[ui]
table_style = "minimal"
""")

        original_exists = os.path.exists

        def mock_exists(path):
            path_str = str(path)
            if path_str == str(user_config_path):
                return True
            if "config.toml" in path_str or "ocmonitor.toml" in path_str:
                return path_str == str(user_config_path)
            return original_exists(path)

        with monkeypatch.context() as m:
            m.setenv("HOME", str(temp_directory))
            m.setattr("ocmonitor.config.os.path.exists", mock_exists)

            manager = ConfigManager()
            assert str(user_config_path) == manager.config_path
            assert manager.config.ui.table_style == "minimal"

    def test_packaged_config_is_final_fallback(self, temp_directory, monkeypatch):
        """Test that packaged config is used when no user/project config exists."""
        packaged_config = Path(config_module.__file__).parent / "config.toml"

        if not packaged_config.exists():
            pytest.skip("Packaged config.toml not found")

        original_exists = os.path.exists

        def mock_exists(path):
            path_str = str(path)
            if ".config/ocmonitor" in path_str:
                return False
            if path_str.endswith("config.toml") or path_str.endswith("ocmonitor.toml"):
                return False
            return original_exists(path)

        with monkeypatch.context() as m:
            m.setenv("HOME", str(temp_directory))
            m.setattr("ocmonitor.config.os.path.exists", mock_exists)

            manager = ConfigManager()
            assert manager.config_path == str(packaged_config)
            assert isinstance(manager.config, Config)
