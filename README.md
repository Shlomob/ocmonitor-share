# 📊 OpenCode Monitor

[![PyPI version](https://img.shields.io/pypi/v/opencode-monitor.svg)](https://pypi.org/project/opencode-monitor/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**OpenCode Monitor is a CLI tool for monitoring and analyzing OpenCode AI coding sessions.**

Transform your OpenCode usage data into beautiful, actionable insights with comprehensive analytics, real-time monitoring, and professional reporting capabilities.

**⚠️ Disclaimer** - This application is not affiliated with OpenCode AI. It is an independent community tool for monitoring OpenCode usage.

[![Sessions Summary Screenshot](screenshots/sessions-summary.png)](screenshots/sessions-summary.png)

## 🌟 Features

### 💼 Professional Analytics
- **📈 Comprehensive Reports** - Daily, weekly, and monthly usage breakdowns
- **💰 Cost Tracking** - Accurate cost calculations for multiple AI models
- **🌍 Multi-Currency Support** - Display costs in USD, GBP, EUR, JPY, CNY, INR, or any currency with live exchange rates
- **📊 Model Analytics** - Detailed breakdown of usage per AI model with `--breakdown` flag
- **🔍 Single Model Deep Dive** - `ocmonitor model <name>` drills into one model with dates, costs, speed, and tool stats
- **📋 Project Analytics** - Track costs and token usage by coding project
- **⏱️ Performance Metrics** - Session duration and processing time tracking
- **📅 Flexible Week Boundaries** - Customize weekly reports with 7 start day options (Monday-Sunday)
- **🚀 Output Speed Tracking** - Average output tokens per second for each model in reports
- **🔗 Workflow Grouping** - Automatically groups main sessions with their sub-agent sessions (explore, etc.)

### 🗄️ Storage Support
- **SQLite Database** - Native support for OpenCode v1.2.0+ SQLite format (`~/.local/share/opencode/opencode.db`)
- **Legacy File Support** - Backwards compatible with pre-v1.2.0 JSON file storage
- **Auto Detection** - Automatically detects and uses the appropriate storage backend
- **Hierarchical Sessions** - Parent/sub-agent relationships from SQLite displayed as tree view

### 🎨 Beautiful User Interface
- **🌈 Rich Terminal UI** - Professional design with clean styling and optimal space utilization
- **📊 Progress Bars** - Visual indicators for cost quotas, context usage, and session time
- **🚥 Color Coding** - Green/yellow/red status indicators based on usage thresholds
- **📱 Live Dashboard** - Real-time monitoring with project names and session titles
- **⏰ Session Time Tracking** - 5-hour session progress bar with color-coded time alerts
- **🔧 Tool Usage Panel** - Track tool success rates (bash, read, edit, etc.) in live dashboard

### 📤 Data Export & Integration
- **📋 CSV Export** - Spreadsheet-compatible exports with metadata
- **🔄 JSON Export** - Machine-readable exports for custom integrations
- **📊 Multiple Report Types** - Sessions, daily, weekly, monthly, model, and project reports
- **📈 Prometheus Metrics** - Real-time metrics endpoint for Grafana/Prometheus integration

## 🚀 Quick Start

### Installation

**Option 1: pip / PyPI (Recommended)**

```bash
pip install opencode-monitor
```

With optional extras:
```bash
pip install "opencode-monitor[charts,export]"
```

**Option 2: uvx (Run without installing)**

```bash
uvx opencode-monitor live
```

**Option 3: uv tool install**

[uv](https://github.com/astral-sh/uv) installs the tool in an isolated environment.

```bash
uv tool install opencode-monitor

# With optional extras
uv tool install "opencode-monitor[charts,export]"

# Easy to upgrade
uv tool upgrade opencode-monitor
```

**Option 4: pipx Installation (Cross Platform)**

[pipx](https://pypa.github.io/pipx/) creates isolated environments and works on all platforms (including Arch Linux, Ubuntu, macOS, etc.).

```bash
pipx install opencode-monitor
```

With optional extras:
```bash
pipx install "opencode-monitor[charts,export]"
```

**Option 5: Install from source**
```bash
git clone https://github.com/Shlomob/ocmonitor-share.git
cd ocmonitor-share
python3 -m pip install -e .
```

**Option 6: Dockerized Installation**
```bash
docker compose build
```

Usage example:
```bash
docker compose run --rm ocmonitor sessions
```

If your host OpenCode data is not in `~/.local/share/opencode`, set `OPENCODE_DATA_DIR` before running:
```bash
OPENCODE_DATA_DIR=/your/path/to/opencode/data/dir docker compose run --rm ocmonitor sessions
```

### Basic Usage

```bash
# Real-time monitoring dashboard
ocmonitor live

# View sessions history
ocmonitor sessions

# Daily usage breakdown (add --breakdown for per-model detail)
ocmonitor daily
ocmonitor daily --breakdown

# Deep dive into a specific model
ocmonitor model claude-sonnet-4-5
```

### Command Reference

| Command | Description |
|---|---|
| `ocmonitor live` | Real-time monitoring dashboard |
| `ocmonitor sessions` | All sessions summary with workflow grouping |
| `ocmonitor session <path>` | Single session detail |
| `ocmonitor daily` | Daily usage breakdown |
| `ocmonitor weekly` | Weekly usage breakdown |
| `ocmonitor monthly` | Monthly usage breakdown |
| `ocmonitor models` | Model usage statistics |
| `ocmonitor model <name>` | Single model deep dive |
| `ocmonitor projects` | Project usage statistics |
| `ocmonitor agents` | List detected agents and types |
| `ocmonitor export <type>` | Export to CSV/JSON |
| `ocmonitor metrics` | Prometheus metrics endpoint |
| `ocmonitor config show` | Show current configuration |

### Global Options

These options can be used with any command:

```bash
ocmonitor --theme light sessions     # Override theme (dark/light)
ocmonitor --verbose daily            # Show detailed error traces
ocmonitor --config /path/config.toml sessions  # Use custom config file
ocmonitor --no-remote sessions       # Disable remote pricing fallback
```

## 📖 Documentation

- **[Quick Start Guide](QUICK_START.md)** - Get up and running in 5 minutes
- **[Manual Test Guide](MANUAL_TEST_GUIDE.md)** - Comprehensive testing instructions
- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute to the project

## 🎯 Use Cases

### Individual Developers
- **Cost Management** - Track your AI usage costs across different models and projects
- **Usage Optimization** - Identify patterns in your coding sessions with session time tracking
- **Performance Monitoring** - Monitor session efficiency and token usage with real-time dashboards
- **Project Analytics** - Understand which projects consume the most AI resources

### Development Teams
- **Team Analytics** - Aggregate usage statistics across team members and projects
- **Budget Planning** - Forecast AI costs based on usage trends and project breakdowns
- **Model Comparison** - Compare performance and costs across different AI models
- **Session Management** - Track coding session durations and productivity patterns

### Organizations
- **Resource Planning** - Plan AI resource allocation and budgets by project
- **Usage Reporting** - Generate professional reports for stakeholders with export capabilities
- **Cost Attribution** - Track AI costs by project, team, and time period
- **Quality Monitoring** - Monitor session lengths and usage patterns for optimization


## 📊 Example Output

> **📸 Screenshots**: The following examples include both text output and clickable screenshots. To add your own screenshots, place PNG files in the `screenshots/` directory with the corresponding filenames.

### Sessions Summary

[![Sessions Summary Screenshot](screenshots/sessions-summary.png)](screenshots/sessions-summary.png)

*Click image to view full-size screenshot of sessions summary output*

#### Workflow Grouping

By default, sessions are grouped into **workflows** - a main session combined with its sub-agent sessions (like `explore`). This gives you a complete picture of your coding session including all agent activity.

```bash
# Sessions with workflow grouping (default)
ocmonitor sessions

# Sessions without grouping (flat list)
ocmonitor sessions --no-group

# Force a specific data source
ocmonitor sessions --source sqlite   # Force SQLite (v1.2.0+)
ocmonitor sessions --source files    # Force legacy file storage

# List detected agents and their types
ocmonitor agents
```

**Workflow Features:**
- Main sessions and sub-agent sessions are visually grouped with tree-style formatting
- Aggregated tokens and costs are shown for the entire workflow
- Sub-agent count displayed in the Agent column (e.g., `+2` means 2 sub-agents)
- Use `--no-group` to see individual sessions without grouping

### Time-Based Reporting

#### `ocmonitor daily|weekly|monthly <path> [--breakdown]`

Time-based usage breakdown with optional per-model cost analysis.

```bash
# Daily breakdown
ocmonitor daily

# Weekly breakdown with per-model breakdown
ocmonitor weekly --breakdown

# Monthly breakdown
ocmonitor monthly

# Weekly with custom start day
ocmonitor weekly --start-day friday --breakdown
```

**`--breakdown` Flag:** Shows token consumption and cost per model within each time period (daily/weekly/monthly), making it easy to see which models are consuming resources.

Supported days: `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday`

### Live Monitoring Commands

#### `ocmonitor live <path>`

Real-time monitoring dashboard that updates automatically. By default, it uses a
full-screen display and restores the terminal prompt when you exit. Use `--inline`
to keep dashboard output in the normal terminal buffer.

```bash
# Start live monitoring (updates every 3 seconds by default)
ocmonitor live

# Custom update interval (in seconds)
ocmonitor live --interval 10

# Keep dashboard output in the normal terminal buffer
ocmonitor live --inline

# Pick a workflow by readable title before launching
# (also enables interactive switching controls by default)
ocmonitor live --pick

# Pin live monitor to a specific workflow/session ID
ocmonitor live --session-id ses_abc123

# Force a specific data source
ocmonitor live --source sqlite    # Force SQLite (v1.2.0+)
ocmonitor live --source files     # Force legacy file storage

# Enable interactive switching while live monitor runs (experimental)
ocmonitor live --interactive-switch
```

If `--session-id` is pinned and the selected workflow is no longer active, live monitoring stops with a clear message.
When both `--session-id` and `--pick` are supplied to `ocmonitor live`, `--session-id` takes precedence and `--pick` is ignored.

**Features:**
- 🔄 Auto-refreshing display with professional UI design
- 📊 Real-time cost tracking with progress indicators
- ⏱️ Live session duration with 5-hour progress bar
- 📈 Token usage updates and context window monitoring
- 🚀 **Output Rate** - Rolling 5-minute window showing output tokens per second
- 🚦 Color-coded status indicators and time alerts
- 📂 Project name display for better context
- 📝 Human-readable session titles instead of cryptic IDs
- 🔗 **Workflow Tracking** - Automatically tracks entire workflow including sub-agents (explore, etc.)
- 🔧 **Tool Usage Stats** - Shows success rates for tools (bash, read, edit, etc.) with color-coded progress bars

[![Live Dashboard Screenshot](screenshots/live_dashboard.png)](screenshots/live_dashboard.png)

*Click image to view full-size screenshot of the live monitoring dashboard*

### Model Usage Breakdown

[![Model Usage Breakdown Screenshot](screenshots/model-usage-breakdown.png)](screenshots/model-usage-breakdown.png)

*Click image to view full-size screenshot of model usage analytics*

```bash
# Filter by timeframe or date range
ocmonitor models --timeframe weekly
ocmonitor models --start-date 2026-01-01 --end-date 2026-02-01
ocmonitor projects --timeframe monthly
ocmonitor projects --start-date 2026-01-01 --end-date 2026-02-01
```

**Model Analytics Features:**
- Per-provider/model token usage and cost breakdown, with separate **Provider** and **Model** columns
- Cost percentage distribution across models
- **Speed Column** - Average output tokens per second for each model
- Session and interaction counts per model

### Single Model Detail

```bash
# Drill into one model by exact or partial name
ocmonitor model claude-sonnet-4-5
ocmonitor model sonnet        # lists all sonnet variants to pick from
ocmonitor model opus -f json  # JSON output
```

**Output:**
```
╭─ Model Detail: claude-sonnet-4-5 ─────────────────────────────╮
│ First Used      2025-09-15                                      │
│ Last Used       2026-02-28                                      │
│ Sessions        42                                              │
│ Days Used       28                                              │
│ Interactions    1,247                                           │
│                                                                 │
│ Input Tokens    2,451,320                                       │
│ Output Tokens   489,210                                         │
│ Cache Read      1,102,400                                       │
│ Cache Write     312,500                                         │
│                                                                 │
│ Total Cost      $47.23                                          │
│ Avg/Day         $1.69                                           │
│ Avg/Session     $1.12                                           │
│                                                                 │
│ Output Speed    62.4 tok/s (p50)                                │
╰─────────────────────────────────────────────────────────────────╯

         Tool Usage for claude-sonnet-4-5
┏━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Tool   ┃ Calls ┃ Success ┃ Failed ┃ Success Rate ┃
┡━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━┩
│ read   │   620 │     598 │     22 │         96%  │
│ edit   │   412 │     389 │     23 │         94%  │
│ bash   │   298 │     285 │     13 │         96%  │
└────────┴───────┴─────────┴────────┴──────────────┘
```

**Features:**
- 🔍 **Fuzzy Matching** - Partial name matches; shows alternatives when multiple models match
- 📋 **Key-Value Panel** - First/last used, sessions, days active, interactions, full token breakdown
- 💰 **Cost Breakdown** - Total cost, average per day, average per session
- 🚀 **Output Speed** - Median output tokens/sec (p50) across all interactions
- 🔧 **Tool Stats** - Per-tool calls, success, failed, color-coded success rate


#### Prometheus Metrics

```bash
# Start metrics server (default port 9090)
ocmonitor metrics

# Custom port
ocmonitor metrics --port 8080

# Scrape metrics
curl http://localhost:9090/metrics
```

**Metrics exposed:**
- `ocmonitor_tokens_input_total{model}` - Input tokens per model
- `ocmonitor_tokens_output_total{model}` - Output tokens per model
- `ocmonitor_cost_dollars_total{model}` - Total cost per model
- `ocmonitor_sessions_total{model}` - Session count per model
- `ocmonitor_session_duration_hours_total` - Total session duration
- `ocmonitor_sessions_by_project{project}` - Sessions by project

**Note:** The `model` label value is in `provider/model` format (e.g., `anthropic/claude-sonnet-4-20250514`).

## ⚙️ Configuration

### Configuration File Location

Create your configuration file at: **`~/.config/ocmonitor/config.toml`**

```bash
# Create the configuration directory
mkdir -p ~/.config/ocmonitor

# Create your configuration file
touch ~/.config/ocmonitor/config.toml
```

### Configuration Options

The tool is highly configurable through the `config.toml` file:

```toml
[paths]
# OpenCode v1.2.0+ SQLite database (preferred)
database_file = "~/.local/share/opencode/opencode.db"
# Legacy file storage (fallback)
messages_dir = "~/.local/share/opencode/storage/message"
export_dir = "./exports"

[ui]
table_style = "rich"       # "rich", "simple", or "minimal"
theme = "dark"             # "dark" or "light"
progress_bars = true
colors = true
live_refresh_interval = 3  # Live dashboard refresh in seconds

[export]
default_format = "csv"
include_metadata = true

[analytics]
default_timeframe = "daily"       # "daily", "weekly", or "monthly"
recent_sessions_limit = 50        # Max sessions to analyze by default

[models]
# Path to local models pricing configuration
config_file = "models.json"
# Remote pricing fallback from models.dev (disabled by default)
remote_fallback = false
remote_url = "https://models.dev/api.json"
remote_timeout_seconds = 8
remote_cache_ttl_hours = 24

[metrics]
# Prometheus metrics server configuration
port = 9090
host = "0.0.0.0"

[currency]
# Display currency (ISO 4217 code): USD, GBP, EUR, CNY, JPY, INR, or custom
code = "USD"
symbol = "$"
# Conversion rate from USD (ignored when remote_rates = true)
rate = 1.0
# Display format: "symbol_prefix" ($1.23) or "code_suffix" (1.23 USD)
display_format = "symbol_prefix"
# Decimal places (auto if not set: JPY=0, most others=2)
# decimals = 2

# Live rate fetching from frankfurter.dev (free, no API key)
remote_rates = false
remote_rates_url = "https://api.frankfurter.dev/v1/latest?base=USD"
remote_rates_timeout_seconds = 8
remote_rates_cache_ttl_hours = 24
remote_rates_cache_path = "~/.cache/ocmonitor/exchange_rates.json"
allow_stale_rates_on_error = true
```

**Configuration File Search Order:**
1. `~/.config/ocmonitor/config.toml` (user overrides - highest priority)
2. `config.toml` (current directory)
3. `ocmonitor.toml` (current directory)
4. Packaged fallback: `ocmonitor/config.toml` (lowest priority, only used if no other config exists)

User settings in `~/.config/ocmonitor/config.toml` take precedence over all other locations.

### Remote Pricing Fallback

OpenCode Monitor supports automatic pricing updates from [models.dev](https://models.dev), a community-maintained pricing database.

**Features:**
- Automatically fetches pricing for new models not in your local `models.json`
- Fill-only mode - never overwrites your local or user-defined prices
- Shared cache across all your projects (`~/.cache/ocmonitor/models_dev_api.json`)
- 24-hour TTL with stale cache fallback on errors
- Works offline using cached data

**Enable Remote Fallback:**
```toml
[models]
remote_fallback = true
```

**Use `--no-remote` to disable for a single run:**
```bash
# Force local-only pricing for this command
ocmonitor --no-remote sessions
```

**Pricing Precedence (highest to lowest):**
1. User override file (`~/.config/ocmonitor/models.json`)
2. Project/local `models.json`
3. models.dev remote fallback (fill-only)

### Currency Conversion

OpenCode Monitor supports displaying costs in your local currency instead of USD.

**Quick Setup:**
```toml
[currency]
code = "GBP"
symbol = "£"
rate = 0.79
```

**Supported Presets:**
| Currency | Code | Symbol | Example Rate |
|----------|------|--------|--------------|
| US Dollar | USD | $ | 1.00 |
| British Pound | GBP | £ | 0.79 |
| Euro | EUR | € | 0.92 |
| Chinese Yuan | CNY | ¥ | 7.24 |
| Japanese Yen | JPY | ¥ | 149.50 |
| Indian Rupee | INR | INR | 83.12 |

**Display Formats:**
- `symbol_prefix` (default): `$1.23` or `£1.23`
- `code_suffix`: `1.23 USD` or `1.23 GBP`

**Live Exchange Rates:**
Enable automatic rate fetching from frankfurter.dev:
```toml
[currency]
code = "EUR"
symbol = "€"
remote_rates = true
```

**JPY/Zero-Decimal Currencies:**
Currencies like JPY automatically use 0 decimal places unless explicitly configured.

## 🛠️ Development

### Prerequisites
- Python 3.8+
- pip package manager

### Setting Up Development Environment

The project uses `pyproject.toml` for modern Python packaging. You can install in development mode using either pip or pipx:

```bash
git clone https://github.com/Shlomob/ocmonitor-share.git
cd ocmonitor-share

# Using pip (editable install)
python3 -m pip install -e ".[dev]"

# Or using pipx (editable install)
pipx install -e ".[dev]"
```

**Install all extras for development:**
```bash
python3 -m pip install -e ".[dev,charts,export]"
```

### Running Tests
```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Legacy test scripts
python3 test_basic.py
python3 test_simple.py
```

### Project Architecture
```
ocmonitor/
├── cli.py                     # Command-line interface (all commands)
├── config.py                  # Configuration management, TOML parsing
├── models/                    # Pydantic data models
│   ├── analytics.py           # DailyUsage, WeeklyUsage, MonthlyUsage, ModelUsageStats
│   ├── session.py             # TokenUsage, TimeData, InteractionFile, SessionData
│   ├── tool_usage.py          # Tool usage tracking models
│   └── workflow.py            # Workflow grouping models
├── services/                  # Business logic layer
│   ├── agent_registry.py      # Agent type detection
│   ├── export_service.py      # CSV/JSON export functionality
│   ├── live_monitor.py        # Real-time dashboard with auto-refresh
│   ├── price_fetcher.py       # Remote pricing from models.dev
│   ├── report_generator.py    # Rich UI report generation
│   ├── session_analyzer.py    # Core session analysis and summaries
│   └── session_grouper.py     # Workflow grouping logic
├── ui/                        # Rich UI components
│   ├── dashboard.py           # Live dashboard UI
│   ├── tables.py              # Table formatting with progress bars
│   └── theme.py               # Dark/light theme support
└── utils/                     # Utility functions
    ├── data_loader.py         # Unified data loading (SQLite/files)
    ├── error_handling.py      # User-friendly error messages
    ├── file_utils.py          # File processing
    ├── formatting.py          # Number/cost formatting utilities
    ├── sqlite_utils.py        # SQLite database access
    └── time_utils.py          # Time formatting and calculations
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on:

- 🐛 Reporting bugs
- 💡 Suggesting features
- 🔧 Setting up development environment
- 📝 Code style and standards
- 🚀 Submitting pull requests

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🏆 Acknowledgments

- **[OpenCode](https://opencode.ai/)** - For creating an excellent AI coding agent that makes development more efficient
- **[ccusage](https://ccusage.com/)** - A similar monitoring tool for Claude Code that inspired features in this project
- **[Click](https://click.palletsprojects.com/)** - Excellent CLI framework
- **[Rich](https://github.com/Textualize/rich)** - Beautiful terminal formatting
- **[Pydantic](https://pydantic-docs.helpmanual.io/)** - Data validation and settings

## 🚀 Status

**🧪 Beta Testing** - This application is currently in beta testing phase. Please report any issues you encounter.


---

*Built with ❤️ for the OpenCode community*
