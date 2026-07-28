# 📚 OpenCode Monitor - Complete Documentation

Welcome to the complete documentation for OpenCode Monitor, a powerful CLI tool for monitoring and analyzing your OpenCode AI coding sessions.

> **📸 Screenshots**: Throughout this documentation, you'll find clickable screenshot references that show actual command outputs. These screenshots are located in the `screenshots/` directory. To add your own screenshots, replace the placeholder PNG files with actual screenshots of your terminal output.

**🆕 Recent Updates**: This documentation reflects the latest improvements including professional UI redesign, project analytics, session time tracking, and enhanced live dashboard features.

## 📖 Table of Contents

1. [Installation](#installation)
2. [Basic Usage](#basic-usage)
3. [Command Reference](#command-reference)
4. [Configuration](#configuration)
5. [Adding New Models](#adding-new-models)
6. [Remote Pricing Fallback](#remote-pricing-fallback)
7. [Currency Conversion](#currency-conversion)
8. [Prometheus Metrics](#prometheus-metrics)
9. [Setting Usage Quotas](#setting-usage-quotas)
10. [Exporting Reports](#exporting-reports)
11. [Configuration Commands](#configuration-commands)
12. [Troubleshooting](#troubleshooting)
13. [Advanced Tips](#advanced-tips)

---

## 🚀 Installation

### Prerequisites

Before installing OpenCode Monitor, ensure you have:
- **Python 3.8+** installed on your system
- **pip** package manager (or **pipx** for isolated installs)
- **OpenCode AI** installed and configured

### Method 1: pipx Installation (Recommended)

[pipx](https://pypa.github.io/pipx/) is the recommended way to install OpenCode Monitor. It creates isolated Python environments and is the safest option across all platforms.

**Advantages:**
- ✅ No dependency conflicts with system packages
- ✅ Works on Arch Linux, Ubuntu, macOS, Windows
- ✅ No sudo required
- ✅ Easy to upgrade, uninstall, or manage multiple versions
- ✅ Automatically adds `ocmonitor` to your PATH

```bash
# Clone the repository
git clone https://github.com/Shlomob/ocmonitor-share.git
cd ocmonitor-share

# Install with pipx (recommended)
pipx install .

# Or with optional extras:
pipx install ".[charts]"    # Includes plotly for visualization
pipx install ".[export]"    # Includes pandas for data export
pipx install ".[charts,export]"  # All extras
```

**Installing pipx:**
- **Arch Linux:** `sudo pacman -S python-pipx`
- **Ubuntu/Debian:** `sudo apt install pipx`
- **macOS:** `brew install pipx`
- **Other:** `python3 -m pip install --user pipx`

### Method 2: Automated Installation (Linux/macOS)

For Linux and macOS users who prefer a traditional virtual environment setup:

```bash
# Clone the repository
git clone https://github.com/Shlomob/ocmonitor-share.git
cd ocmonitor-share

# Run the automated installer
./install.sh
```

The installer will:
- ✅ Check Python version compatibility (3.8+)
- ✅ Create a virtual environment
- ✅ Install all required dependencies from `pyproject.toml`
- ✅ Configure PATH settings automatically
- ✅ Verify the installation

### Method 3: Manual Installation

For development or custom setups:

```bash
# Clone the repository
git clone https://github.com/Shlomob/ocmonitor-share.git
cd ocmonitor-share

# Install Python dependencies
python3 -m pip install -r requirements.txt

# Install the package in development mode
python3 -m pip install -e ".[dev,charts,export]"
```

**Note:** The project uses `pyproject.toml` for modern Python packaging. All dependencies are properly declared and will be installed automatically.

### Verify Installation

After installation, verify everything works:

```bash
# Check if ocmonitor is accessible
ocmonitor --version
ocmonitor --help

# Test with sample data
ocmonitor sessions test_sessions/

# Verify configuration
ocmonitor config show
```

**Troubleshooting pipx installs:**
If `ocmonitor` command is not found after pipx install:
```bash
# Ensure pipx PATH is set up
pipx ensurepath

# Or manually add to your shell profile (~/.bashrc, ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"
```

### Configuration Setup

After installation, set up your personal configuration:

```bash
# Create configuration directory
mkdir -p ~/.config/ocmonitor

# Copy default configuration (if available in project)
cp config.toml ~/.config/ocmonitor/config.toml

# Or create a new configuration file
touch ~/.config/ocmonitor/config.toml

# Edit your configuration
nano ~/.config/ocmonitor/config.toml
```

Your configuration file should contain:
```toml
[paths]
messages_dir = "~/.local/share/opencode/storage/message"
export_dir = "./exports"

[ui]
table_style = "rich"
progress_bars = true
colors = true
```

### PATH Configuration (If Needed)

If you get "command not found" errors:

```bash
# Find your Python user base
python3 -m site --user-base

# Add to your shell profile (~/.bashrc or ~/.zshrc)
export PATH="$(python3 -m site --user-base)/bin:$PATH"

# Reload your shell
source ~/.bashrc  # or ~/.zshrc
```

---

## 🎯 Basic Usage

### Quick Start Example

```bash
# Show current configuration
ocmonitor config show

# Analyze all your sessions (auto-detects SQLite or files)
ocmonitor sessions

# Get a weekly breakdown
ocmonitor weekly

# Start live monitoring
ocmonitor live

# Force specific data source
ocmonitor live --source sqlite
ocmonitor sessions --source files
```

### Default OpenCode Storage Locations

OpenCode v1.2.0+ uses SQLite database:
```
~/.local/share/opencode/opencode.db
```

Legacy versions (< v1.2.0) use flat JSON files:
```
~/.local/share/opencode/storage/message/
```

The tool automatically detects and uses the appropriate source. Use `--source` flag to force a specific backend.

---

## 📋 Command Reference

### Global Options

These options can be used with any command:

| Option | Description | Example |
|--------|-------------|---------|
| `--config, -c` | Path to configuration file | `--config /path/to/config.toml` |
| `--theme, -t` | Set UI theme (`dark` or `light`) | `--theme light` |
| `--verbose, -v` | Enable verbose output | `--verbose` |
| `--no-remote` | Disable remote pricing fallback | `--no-remote` |
| `--version` | Show version information | `--version` |

#### The `--no-remote` Flag

Use `--no-remote` to disable remote pricing fallback for a single command:

```bash
# Force local-only pricing for this session
ocmonitor --no-remote sessions

# Works with any command
ocmonitor --no-remote models
ocmonitor --no-remote daily --breakdown
```

This is useful when:
- You want to ensure only local pricing is used
- You're working offline and want to avoid fetch attempts
- Debugging pricing discrepancies

### 1. Session Analysis Commands

#### `ocmonitor session <path>`
Analyze a single coding session in detail.

```bash
# Analyze a specific session directory
ocmonitor session ~/.local/share/opencode/storage/message/ses_20250118_143022

# With JSON output
ocmonitor session ~/.local/share/opencode/storage/message/ses_20250118_143022 --format json
```

**Example Output:**

[![Session Analysis Screenshot](screenshots/session-analysis.png)](screenshots/session-analysis.png)

*Click image to view full-size screenshot of session analysis output*


```

#### `ocmonitor sessions [path]`
Analyze all sessions with summary statistics. Auto-detects SQLite database or legacy files.

```bash
# Analyze all sessions (auto-detect source)
ocmonitor sessions

# Specify path (legacy files only)
ocmonitor sessions ~/.local/share/opencode/storage/message

# Limit to recent sessions
ocmonitor sessions --limit 10

# Force specific source
ocmonitor sessions --source sqlite
ocmonitor sessions --source files

# JSON format for programmatic use
ocmonitor sessions --format json
```

**Example Output:**

[![Sessions Summary Screenshot](screenshots/sessions-summary.png)](screenshots/sessions-summary.png)

*Click image to view full-size screenshot of sessions summary output*

```

### 2. Time-Based Analysis Commands

#### `ocmonitor daily <path>`
Daily usage breakdown with cost and token analysis.

```bash
# Daily breakdown
ocmonitor daily ~/.local/share/opencode/storage/message

# With per-model breakdown
ocmonitor daily ~/.local/share/opencode/storage/message --breakdown

# JSON output
ocmonitor daily ~/.local/share/opencode/storage/message --format json
```

**Example Output:**

[![Daily Usage Breakdown Screenshot](screenshots/daily-usage-breakdown.png)](screenshots/daily-usage-breakdown.png)

*Click image to view full-size screenshot of daily usage breakdown*

```

#### `ocmonitor weekly <path> [--start-day <day>]`
Weekly usage patterns and trends with customizable week start days.

```bash
# Default (Monday start)
ocmonitor weekly ~/.local/share/opencode/storage/message

# Custom week start days
ocmonitor weekly ~/.local/share/opencode/storage/message --start-day sunday
ocmonitor weekly ~/.local/share/opencode/storage/message --start-day friday

# With per-model breakdown
ocmonitor weekly ~/.local/share/opencode/storage/message --start-day sunday --breakdown

# Specific year with custom week start
ocmonitor weekly ~/.local/share/opencode/storage/message --year 2025 --start-day wednesday
```

**Supported Days:** `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday`

**Features:**
- 📅 Customize week boundaries to match your calendar preference
- 🗓️ US standard (Sunday), European (Monday), business week (Friday), etc.
- 📊 Date range display shows actual week boundaries
- 🎯 Table title indicates selected week start day

#### `ocmonitor monthly <path>`
Monthly usage analysis and cost tracking.

```bash
# Monthly breakdown
ocmonitor monthly ~/.local/share/opencode/storage/message

# With per-model breakdown
ocmonitor monthly ~/.local/share/opencode/storage/message --breakdown
```

### 3. Model Analysis Commands

#### `ocmonitor models <path>`
Detailed breakdown of usage per AI model.

```bash
# Model usage statistics
ocmonitor models ~/.local/share/opencode/storage/message

# JSON format
ocmonitor models ~/.local/share/opencode/storage/message --format json
```

**Example Output:**

[![Model Usage Analysis Screenshot](screenshots/model-usage-analysis.png)](screenshots/model-usage-analysis.png)

*Click image to view full-size screenshot of model usage analytics*

#### `ocmonitor model <name>`
Deep-dive detail for a single model. The name is fuzzy-matched against all known model names in the database.

```bash
# Exact or partial name — fuzzy matched
ocmonitor model claude-sonnet-4-5
ocmonitor model sonnet          # lists all matching variants
ocmonitor model opus -f json    # JSON output
ocmonitor model nonexistent     # shows "No model found" + available list
```

**Fuzzy Matching Behavior:**

| Situation | Result |
|-----------|--------|
| 0 matches | Shows "No model found" and lists all available model names |
| 1 match (or exact name) | Displays full detail panel + tool table |
| >1 matches | Lists candidates with "Did you mean one of these?" |

**Output Layout:**

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
│ grep   │   156 │     154 │      2 │         99%  │
│ glob   │   134 │     134 │      0 │        100%  │
└────────┴───────┴─────────┴────────┴──────────────┘

Total tool calls: 1,620  1,560 succeeded  60 failed  Overall: 96%
```

**Options:**

| Option | Description | Example |
|--------|-------------|---------|
| `--format, -f` | Output format (`table`, `json`, `csv`) | `-f json` |

**Notes:**
- Requires SQLite database (OpenCode v1.2.0+). File-based storage is not supported for this command.
- Success rate colors: green ≥90%, yellow ≥70%, red <70%
- Output speed (p50) excludes tool-call-only interactions and interactions under 100 output tokens

#### `ocmonitor projects <path>`
Analyze AI usage costs and token consumption by coding project.

```bash
# Project usage breakdown
ocmonitor projects ~/.local/share/opencode/storage/message

# Filter by date range
ocmonitor projects ~/.local/share/opencode/storage/message --start-date 2024-01-01 --end-date 2024-01-31

# JSON format for detailed analysis
ocmonitor projects ~/.local/share/opencode/storage/message --format json

# CSV format for spreadsheet analysis
ocmonitor projects ~/.local/share/opencode/storage/message --format csv
```

**Features:**
- 📊 **Project Breakdown** - Shows sessions, interactions, tokens, and costs per project
- 📈 **Summary Statistics** - Total projects, sessions, interactions, tokens, and cost
- 📅 **Activity Tracking** - First and last activity dates for each project
- 🤖 **Model Usage** - Lists AI models used for each project
- 📤 **Export Support** - Full export capabilities with detailed metadata

**Example Output:**
```
                             Project Usage Breakdown
┏━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Project   ┃ Sessions ┃ Interactions ┃ Total Tokens ┃    Cost ┃ Models Used     ┃
┡━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ ocmonitor │        5 │           12 │       25,340 │ $0.0512 │ claude-sonnet-… │
│ myapp     │        3 │            8 │       18,200 │ $0.0364 │ claude-opus-4   │
│ website   │        2 │            4 │        8,150 │ $0.0163 │ grok-code       │
└───────────┴──────────┴──────────────┴──────────────┴─────────┴─────────────────┘
╭────────────────────────────────── Summary ───────────────────────────────────╮
│ Total: 3 projects, 10 sessions, 24 interactions, 51,690 tokens, $0.10        │
╰──────────────────────────────────────────────────────────────────────────────╯
```



### 4. Live Monitoring Commands

#### `ocmonitor live <path>`
Real-time monitoring dashboard that updates automatically. By default, it uses a
full-screen display and restores the terminal prompt when you exit. Use `--inline`
to keep dashboard output in the normal terminal buffer.

```bash
# Start live monitoring (updates every 3 seconds by default)
ocmonitor live ~/.local/share/opencode/storage/message

# Custom refresh interval (in seconds)
ocmonitor live ~/.local/share/opencode/storage/message --interval 10

# Keep dashboard output in the normal terminal buffer
ocmonitor live ~/.local/share/opencode/storage/message --inline
```

**Features:**
- 🔄 Auto-refreshing display with professional UI redesign
- 📊 Real-time cost tracking with progress indicators  
- ⏱️ Live session duration with 5-hour progress bar and color-coded time alerts
- 📈 Token usage updates and context window monitoring
- 🚦 Color-coded status indicators (green/orange/yellow/red based on time elapsed)
- 📂 Project name display for better context awareness
- 📝 Human-readable session titles replacing cryptic session IDs
- 🎨 Clean, professional styling with optimal space utilization
- 🔧 **Tool Usage Stats** - Real-time success rates for tools (bash, read, edit, etc.)

[![Live Dashboard Screenshot](screenshots/live_dashboard.png)](screenshots/live_dashboard.png)

*Click image to view full-size screenshot of the live monitoring dashboard*

### 5. Metrics Commands

#### `ocmonitor metrics [--port] [--host]`
Start a Prometheus metrics server for Grafana/Prometheus integration.

```bash
# Start metrics server (default port 9090)
ocmonitor metrics

# Custom port
ocmonitor metrics --port 8080

# Custom host
ocmonitor metrics --host 127.0.0.1

# Scrape metrics
curl http://localhost:9090/metrics
```

**Features:**
- 📊 **Prometheus Format** - Exposes metrics in Prometheus exposition format
- 🔄 **Real-time Data** - Fresh session data loaded on each scrape
- 🏷️ **Labeled Metrics** - Per-model and per-project labels for granular queries
- ⚙️ **Configurable** - Custom host and port via CLI flags or config

**Metrics Exposed:**
- `ocmonitor_tokens_input_total{model}` - Input tokens per model
- `ocmonitor_tokens_output_total{model}` - Output tokens per model
- `ocmonitor_cost_dollars_total{model}` - Total cost per model
- `ocmonitor_sessions_total{model}` - Session count per model
- `ocmonitor_session_duration_hours_total` - Total session duration
- `ocmonitor_sessions_by_project{project}` - Sessions by project

**Note:** Requires `prometheus_client>=0.17.0`. Install with `pip install prometheus_client>=0.17.0`

---

## ⚙️ Configuration

### Configuration File Setup

OpenCode Monitor uses a configuration file located at: **`~/.config/ocmonitor/config.toml`**

#### Create Configuration File

```bash
# Create the configuration directory
mkdir -p ~/.config/ocmonitor

# Create your configuration file
touch ~/.config/ocmonitor/config.toml
```

#### Configuration File Search Order

OpenCode Monitor searches for configuration files in this order:
1. **`~/.config/ocmonitor/config.toml`** (recommended user location)
2. `config.toml` (current working directory)
3. `ocmonitor.toml` (current working directory)
4. Project directory fallback

### Data Source Configuration

OpenCode Monitor supports both SQLite database (OpenCode v1.2.0+) and legacy JSON files (< v1.2.0).

#### Method 1: Edit Configuration File

Edit your `~/.config/ocmonitor/config.toml` file:

```toml
[paths]
# OpenCode v1.2.0+ SQLite database (preferred)
database_file = "~/.local/share/opencode/opencode.db"
# Legacy file storage (fallback for pre-v1.2.0)
messages_dir = "~/.local/share/opencode/storage/message"
# Directory for exports
export_dir = "./my-exports"
```

#### Method 2: Environment Variables

```bash
# SQLite database path
export OCMONITOR_DATABASE_FILE="/custom/path/to/opencode.db"

# Legacy messages directory
export OCMONITOR_MESSAGES_DIR="/custom/path/to/messages"

# Use in commands
ocmonitor sessions
```

#### Method 3: Command Line Override

```bash
# Force specific source
ocmonitor sessions --source sqlite
ocmonitor sessions --source files

# With legacy file path
ocmonitor sessions --source files /custom/path/to/messages
```

### Full Configuration Options

Here's a complete `~/.config/ocmonitor/config.toml` with all available options:

```toml
# OpenCode Monitor Configuration

[paths]
# OpenCode v1.2.0+ SQLite database (preferred)
database_file = "~/.local/share/opencode/opencode.db"
# Legacy path to OpenCode messages directory (< v1.2.0)
messages_dir = "~/.local/share/opencode/storage/message"
# Directory for exports
export_dir = "./exports"

[ui]
# Table style: "rich", "simple", "minimal"
table_style = "rich"
# Enable progress bars
progress_bars = true
# Enable colors in output
colors = true
# Refresh interval for live dashboard (seconds)
live_refresh_interval = 5

[export]
# Default export format: "csv", "json"
default_format = "csv"
# Include metadata in exports
include_metadata = true
# Include raw data in exports
include_raw_data = false

[models]
# Path to models pricing configuration
config_file = "models.json"

# Remote pricing fallback from models.dev
# Automatically fetches pricing for models not in local files
remote_fallback = false
remote_url = "https://models.dev/api.json"
remote_timeout_seconds = 8
remote_cache_ttl_hours = 24
remote_cache_path = "~/.cache/ocmonitor/models_dev_api.json"
user_file = "~/.config/ocmonitor/models.json"
allow_stale_cache_on_error = true

[analytics]
# Default timeframe for reports: "daily", "weekly", "monthly"
default_timeframe = "daily"
# Number of recent sessions to analyze by default
recent_sessions_limit = 50

[quotas]
# Daily spending limits per model (in USD)
daily_limits = { claude-sonnet-4 = 10.0, claude-opus-4 = 20.0 }
# Monthly spending limits
monthly_limits = { claude-sonnet-4 = 200.0, claude-opus-4 = 400.0 }
# Enable quota warnings
enable_warnings = true

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

---

## 🤖 Adding New Models

### Understanding the Models Configuration

Models are defined in the `models.json` file. Each model includes pricing and technical specifications.

### Current Models Format

Models are keyed by `provider/model-id`, where `provider` is the canonical provider ID
(e.g., `anthropic`, `openai`, `google`) and `model-id` matches the model identifier
stored by OpenCode.

```json
{
  "anthropic/claude-sonnet-4-20250514": {
    "input": 3.0,
    "output": 15.0,
    "cacheWrite": 3.75,
    "cacheRead": 0.30,
    "contextWindow": 200000,
    "sessionQuota": 6.00,
    "description": "Claude Sonnet 4 (2025-05-14)"
  },
  "anthropic/claude-opus-4": {
    "input": 15.0,
    "output": 75.0,
    "cacheWrite": 18.75,
    "cacheRead": 1.50,
    "contextWindow": 200000,
    "sessionQuota": 10.00,
    "description": "Claude Opus 4"
  },
  "opencode/grok-code": {
    "input": 0.0,
    "output": 0.0,
    "cacheWrite": 0.0,
    "cacheRead": 0.0,
    "contextWindow": 256000,
    "sessionQuota": 0.0,
    "description": "Grok Code (Free)"
  }
}
```

### Adding a New Model

#### Step 1: Edit models.json

Add your new model to the `models.json` file using `provider/model-id` as the key:

```json
{
  "existing-models": "...",
  
  "provider/new-ai-model": {
    "input": 5.0,
    "output": 25.0,
    "cacheWrite": 6.25,
    "cacheRead": 0.50,
    "contextWindow": 128000,
    "sessionQuota": 15.0,
    "description": "New AI Model"
  },
  
  "provider/another-model": {
    "input": 0.0,
    "output": 0.0,
    "cacheWrite": 0.0,
    "cacheRead": 0.0,
    "contextWindow": 100000,
    "sessionQuota": 0.0,
    "description": "Another Free Model"
  }
}
```

#### Step 2: Verify the Addition

Test that your new model is recognized:

```bash
# Check if the model appears in configuration
ocmonitor config show

# Test with session data that uses the new model
ocmonitor sessions /path/to/sessions
```

#### Step 3: Pricing Lookup Chain

OCMonitor uses a 5-step backward-compatible lookup chain when resolving pricing for
a session interaction. You only need to add a single `provider/model-id` entry — bare
model IDs (legacy files) continue to work automatically:

1. `provider_id/model_id` — exact provider+model match
2. `provider_id/normalize(model_id)` — provider + normalized model
3. `model_id` — bare exact match (old `models.json` files keep working)
4. `normalize(model_id)` — bare normalized
5. Scan `*/model_id` — any provider, model-only fallback

```json
{
  "provider/model-name": {
    "input": 2.0,
    "output": 10.0,
    "cacheWrite": 2.5,
    "cacheRead": 0.20,
    "contextWindow": 150000,
    "sessionQuota": 8.0,
    "description": "Provider Model"
  }
}
```

### Model Configuration Fields

| Field | Description | Required | Example |
|-------|-------------|----------|---------|
| `input` | Cost per 1M input tokens (USD) | ✅ | `3.0` |
| `output` | Cost per 1M output tokens (USD) | ✅ | `15.0` |
| `cacheWrite` | Cost per 1M cache write tokens (USD) | ✅ | `3.75` |
| `cacheRead` | Cost per 1M cache read tokens (USD) | ✅ | `0.30` |
| `contextWindow` | Maximum context window size | ✅ | `200000` |
| `sessionQuota` | Maximum session cost quota (USD) | ✅ | `6.00` |
| `description` | Human-readable model name | ❌ | `"Claude Sonnet 4"` |

### Field Details

- **`input`**: Base cost for processing input tokens (prompt tokens)
- **`output`**: Cost for generating output tokens (response tokens)  
- **`cacheWrite`**: Cost for writing tokens to cache (context caching feature)
- **`cacheRead`**: Cost for reading tokens from cache (much cheaper than input)
- **`contextWindow`**: Maximum number of tokens the model can process in one request
- **`sessionQuota`**: Maximum cost limit per session (0 = no limit)
- **`description`**: Optional human-readable name for display purposes

### Free Models

For free models, set all costs to `0.0`:

```json
{
  "free-model": {
    "input": 0.0,
    "output": 0.0,
    "cacheWrite": 0.0,
    "cacheRead": 0.0,
    "contextWindow": 100000,
    "sessionQuota": 0.0,
    "description": "Free AI Model"
  }
}
```

---

## 🌐 Remote Pricing Fallback

OpenCode Monitor supports automatic pricing updates from [models.dev](https://models.dev), a community-maintained database of AI model pricing.

### What is models.dev?

[models.dev](https://models.dev) is an open-source project that maintains up-to-date pricing information for AI models from various providers. It provides a standardized API for accessing model costs, context windows, and rate limits.

### How Remote Fallback Works

When enabled, OpenCode Monitor will:
1. **Check local pricing first** - Uses your local `models.json` and user override file
2. **Fetch from models.dev** - Downloads current pricing for any missing models
3. **Cache the results** - Stores data locally for 24 hours to minimize API calls
4. **Merge intelligently** - Only fills gaps; never overwrites your local prices

### Pricing Precedence

Models are resolved in this order (highest to lowest priority):

1. **OpenCode's pre-computed cost** - Used directly when present in session data
2. **User override file** (`~/.config/ocmonitor/models.json`) - Your personal overrides
3. **Project/local `models.json`** - Project-specific pricing
4. **models.dev remote fallback** - Community pricing (fill-only, never overwrites)

### Enabling Remote Fallback

Edit your `~/.config/ocmonitor/config.toml`:

```toml
[models]
# Enable remote pricing fallback
remote_fallback = true

# Optional: customize settings
remote_url = "https://models.dev/api.json"
remote_timeout_seconds = 8
remote_cache_ttl_hours = 24
remote_cache_path = "~/.cache/ocmonitor/models_dev_api.json"
user_file = "~/.config/ocmonitor/models.json"
allow_stale_cache_on_error = true
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `remote_fallback` | Enable remote pricing fetch | `false` |
| `remote_url` | models.dev API endpoint | `https://models.dev/api.json` |
| `remote_timeout_seconds` | HTTP request timeout | `8` |
| `remote_cache_ttl_hours` | Cache validity period | `24` |
| `remote_cache_path` | Local cache file location | `~/.cache/ocmonitor/models_dev_api.json` |
| `user_file` | User pricing overrides | `~/.config/ocmonitor/models.json` |
| `allow_stale_cache_on_error` | Use expired cache if fetch fails | `true` |

### Disabling Remote Fallback

**For a single command:**
```bash
ocmonitor --no-remote sessions
ocmonitor --no-remote models
```

**Globally:**
```toml
[models]
remote_fallback = false
```

### Shared Cache

The remote pricing cache is stored at `~/.cache/ocmonitor/models_dev_api.json` and is shared across all your OpenCode Monitor projects. This means:
- ✅ One download serves all projects
- ✅ Works offline after first fetch
- ✅ Automatically refreshes after TTL expires
- ✅ Uses file locking for safe concurrent access

### Offline Behavior

If remote fetch fails (no internet, API down):
- ✅ Uses cached data if available (even if expired)
- ✅ Falls back to local-only pricing
- ✅ CLI continues working without errors
- ✅ No pricing gaps for known models

### User Override File

Create `~/.config/ocmonitor/models.json` for personal pricing overrides:

```json
{
  "my-custom-model": {
    "input": 5.0,
    "output": 25.0,
    "cacheWrite": 6.25,
    "cacheRead": 0.50,
    "contextWindow": 128000,
    "sessionQuota": 15.0
  },
  "claude-sonnet-4": {
    "input": 2.5,
    "output": 12.0,
    "sessionQuota": 5.0
  }
}
```

User overrides have **highest priority** and will overwrite any local or remote pricing.

### Pricing Examples

#### Premium Model (with caching support)
```json
{
  "anthropic.claude-sonnet-4-20250514-v1:0": {
    "input": 3.0,
    "output": 15.0,
    "cacheWrite": 3.75,
    "cacheRead": 0.30,
    "contextWindow": 1000000,
    "sessionQuota": 10.0,
    "description": "Claude Sonnet 4 (2025-05-14)"
  }
}
```

#### Basic Model (no caching)
```json
{
  "gpt-4o": {
    "input": 2.50,
    "output": 10.0,
    "cacheWrite": 0.0,
    "cacheRead": 0.0,
    "contextWindow": 128000,
    "sessionQuota": 0.0,
    "description": "GPT-4o"
  }
  }
}

---

## 💱 Currency Conversion

OpenCode Monitor supports displaying costs in your local currency instead of USD. All internal calculations remain in USD; conversion happens only at display and export time.

### Quick Setup

Edit your `~/.config/ocmonitor/config.toml`:

```toml
[currency]
code = "GBP"
symbol = "£"
rate = 0.79
```

### Supported Preset Currencies

| Currency | Code | Symbol | Example Rate |
|----------|------|--------|--------------|
| US Dollar | USD | $ | 1.00 |
| British Pound | GBP | £ | 0.79 |
| Euro | EUR | € | 0.92 |
| Chinese Yuan | CNY | ¥ | 7.24 |
| Japanese Yen | JPY | ¥ | 149.50 |
| Indian Rupee | INR | ₹ | 83.12 |

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `code` | ISO 4217 currency code | `USD` |
| `symbol` | Currency symbol | `$` |
| `rate` | Conversion rate from USD | `1.0` |
| `display_format` | `symbol_prefix` ($1.23) or `code_suffix` (1.23 USD) | `symbol_prefix` |
| `decimals` | Decimal places (auto if not set) | `null` |
| `remote_rates` | Enable live rate fetching | `false` |
| `remote_rates_url` | Exchange rate API endpoint | frankfurter.dev |
| `remote_rates_timeout_seconds` | API request timeout | `8` |
| `remote_rates_cache_ttl_hours` | Cache validity period | `24` |

### Display Formats

**Symbol Prefix (default):**
```toml
display_format = "symbol_prefix"
# Output: $1.23, £0.99, €5.50
```

**Code Suffix:**
```toml
display_format = "code_suffix"
# Output: 1.23 USD, 0.99 GBP, 5.50 EUR
```

### Zero-Decimal Currencies

Currencies like JPY, KRW, and VND automatically use 0 decimal places unless explicitly configured:

```toml
[currency]
code = "JPY"
symbol = "¥"
rate = 149.50
# Output: ¥150 (0 decimals auto-applied)
```

### Live Exchange Rates

Enable automatic rate fetching from [frankfurter.dev](https://www.frankfurter.dev/) (free, no API key required):

```toml
[currency]
code = "EUR"
symbol = "€"
remote_rates = true
remote_rates_timeout_seconds = 8
remote_rates_cache_ttl_hours = 24
```

**How it works:**
1. Checks cache freshness before fetching
2. Downloads latest rates from frankfurter.dev
3. Caches results locally (24-hour TTL by default)
4. Falls back to stale cache if fetch fails
5. Falls back to configured `rate` if no cache available

**Cache location:** `~/.cache/ocmonitor/exchange_rates.json`

### Exporting with Currency

Exported reports include currency metadata:

**JSON export:**
```json
{
  "metadata": {
    "currency": {
      "code": "GBP",
      "rate": 0.79
    }
  }
}
```

**CSV export:**
```csv
# Currency: GBP (rate: 0.79 from USD)
session_id,cost,model
ses_123,$1.23,claude-sonnet-4
```

---

## 📊 Prometheus Metrics

OpenCode Monitor now includes a Prometheus metrics endpoint, allowing you to scrape session analytics into Prometheus and visualize them in Grafana.

### What is Prometheus Metrics?

Prometheus is an open-source monitoring system that collects metrics from configured targets. The `ocmonitor metrics` command starts a lightweight HTTP server that exposes session analytics in Prometheus exposition format, enabling real-time monitoring and alerting.

### Starting the Metrics Server

```bash
# Start metrics server with default settings (port 9090)
ocmonitor metrics

# Custom port
ocmonitor metrics --port 8080

# Custom host and port
ocmonitor metrics --host 127.0.0.1 --port 9090
```

**Startup Banner:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📊 OpenCode Monitor Metrics Server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌐 Endpoint: http://0.0.0.0:9090/metrics

Press Ctrl+C to stop
```

### Metrics Exposed

All metrics are exposed at `http://localhost:9090/metrics` (or your configured host/port):

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `ocmonitor_tokens_input_total` | Gauge | `model` | Total input tokens |
| `ocmonitor_tokens_output_total` | Gauge | `model` | Total output tokens |
| `ocmonitor_tokens_cache_read_total` | Gauge | `model` | Total cache read tokens |
| `ocmonitor_tokens_cache_write_total` | Gauge | `model` | Total cache write tokens |
| `ocmonitor_cost_dollars_total` | Gauge | `model` | Total cost in USD |
| `ocmonitor_sessions_total` | Gauge | `model` | Total number of sessions |
| `ocmonitor_interactions_total` | Gauge | `model` | Total number of interactions |
| `ocmonitor_output_rate_tokens_per_second` | Gauge | `model` | P50 output rate (tok/s) |
| `ocmonitor_session_duration_hours_total` | Gauge | _(none)_ | Total session duration across all models |
| `ocmonitor_sessions_by_project` | Gauge | `project` | Sessions grouped by project |

### Scraping Metrics

**Using curl:**
```bash
curl http://localhost:9090/metrics
```

**Sample output:**
```
# HELP ocmonitor_tokens_input_total Total input tokens
# TYPE ocmonitor_tokens_input_total gauge
ocmonitor_tokens_input_total{model="claude-sonnet-4-20250514"} 2451320.0
ocmonitor_tokens_input_total{model="claude-opus-4"} 892340.0

# HELP ocmonitor_cost_dollars_total Total cost in USD
# TYPE ocmonitor_cost_dollars_total gauge
ocmonitor_cost_dollars_total{model="claude-sonnet-4-20250514"} 47.23
ocmonitor_cost_dollars_total{model="claude-opus-4"} 89.45

# HELP ocmonitor_session_duration_hours_total Total session duration in hours
# TYPE ocmonitor_session_duration_hours_total gauge
ocmonitor_session_duration_hours_total 142.5
```

### Prometheus Configuration

Add ocmonitor to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'ocmonitor'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 30s
```

### Grafana Dashboard

Create a simple Grafana dashboard with PromQL queries:

**Total Cost by Model:**
```promql
ocmonitor_cost_dollars_total
```

**Total Tokens Over Time:**
```promql
sum(ocmonitor_tokens_input_total) + sum(ocmonitor_tokens_output_total)
```

**Sessions by Project:**
```promql
ocmonitor_sessions_by_project
```

### Configuration

Add to `~/.config/ocmonitor/config.toml`:

```toml
[metrics]
port = 9090
host = "0.0.0.0"
```

**Environment Variables:**
```bash
export OCMONITOR_METRICS_PORT=9090
export OCMONITOR_METRICS_HOST=0.0.0.0
```

### How It Works

The metrics server uses Prometheus's **Custom Collector** pattern:

1. **On each scrape**, the `collect()` method is called
2. **Fresh data is loaded** from the SQLite database
3. **Metrics are computed** using the existing SessionAnalyzer
4. **GaugeMetricFamily objects** are yielded with current values

This design ensures:
- ✅ No background threads or polling
- ✅ Prometheus controls data freshness via scrape interval
- ✅ Always reflects the latest session data
- ✅ Graceful degradation on errors (returns zero-valued metrics)

### Dependencies

The metrics feature requires `prometheus_client`:

```bash
# Install with metrics support
pip install "ocmonitor[metrics]"

# Or manually
pip install prometheus_client>=0.17.0
```

### Troubleshooting

**Port already in use:**
```bash
ocmonitor metrics --port 8080  # Use a different port
```

**Missing dependency:**
```bash
pip install prometheus_client>=0.17.0
```

**Graceful shutdown:**
Press `Ctrl+C` to stop the server cleanly.

---

## 💰 Setting Usage Quotas

### Understanding Quotas

Quotas help you monitor and control your AI usage costs by setting spending limits.

### Configuring Quotas

#### Method 1: Configuration File

Edit `~/.config/ocmonitor/config.toml` to set quota limits:

```toml
[quotas]
# Daily spending limits per model (in USD)
daily_limits = { 
    claude-sonnet-4 = 10.0, 
    claude-opus-4 = 20.0,
    claude-opus-4.1 = 25.0
}

# Weekly spending limits
weekly_limits = { 
    claude-sonnet-4 = 50.0, 
    claude-opus-4 = 100.0 
}

# Monthly spending limits
monthly_limits = { 
    claude-sonnet-4 = 200.0, 
    claude-opus-4 = 400.0,
    "*" = 500.0  # Total limit across all models
}

# Enable quota warnings
enable_warnings = true

# Warning threshold (percentage of quota)
warning_threshold = 80.0

# Action when quota exceeded: "warn", "block"
quota_action = "warn"
```

#### Method 2: Environment Variables

Set quotas using environment variables:

```bash
# Daily limits
export OCMONITOR_DAILY_CLAUDE_SONNET_4=10.0
export OCMONITOR_DAILY_CLAUDE_OPUS_4=20.0

# Monthly limits
export OCMONITOR_MONTHLY_TOTAL=500.0
```

### Quota Examples

#### Basic Daily Limits

```toml
[quotas]
daily_limits = { 
    claude-sonnet-4 = 15.0,  # $15/day for Sonnet
    claude-opus-4 = 30.0     # $30/day for Opus
}
enable_warnings = true
```

#### Comprehensive Quota Setup

```toml
[quotas]
# Daily limits per model
daily_limits = { 
    claude-sonnet-4 = 10.0,
    claude-opus-4 = 20.0,
    "*" = 35.0  # Total daily limit
}

# Weekly limits
weekly_limits = { 
    claude-sonnet-4 = 60.0,
    claude-opus-4 = 120.0,
    "*" = 200.0
}

# Monthly limits
monthly_limits = { 
    claude-sonnet-4 = 250.0,
    claude-opus-4 = 500.0,
    "*" = 800.0
}

# Warning settings
enable_warnings = true
warning_threshold = 75.0  # Warn at 75% of quota
email_notifications = "admin@example.com"
```

### Viewing Quota Status

Check your current quota usage:

```bash
# Show quota status in daily report
ocmonitor daily ~/.local/share/opencode/storage/message --show-quotas

# Show quota status in model breakdown
ocmonitor models ~/.local/share/opencode/storage/message --show-quotas
```


---

## 📤 Exporting Reports

### Export Command Overview

OpenCode Monitor provides powerful export capabilities for creating reports and integrating with other tools.

### Basic Export Syntax

```bash
ocmonitor export <report_type> [path] [options]
```

### Export Types

#### 1. Sessions Export

Export detailed session data:

```bash
# Export all sessions to CSV
ocmonitor export sessions --format csv --output sessions_report.csv

# Export to JSON
ocmonitor export sessions --format json --output sessions_data.json

# Export recent sessions only
ocmonitor export sessions --limit 50 --format csv

# Force SQLite source
ocmonitor export sessions --source sqlite --format csv
```

#### 2. Daily Reports Export

```bash
# Export daily breakdown
ocmonitor export daily ~/.local/share/opencode/storage/message --format csv --output daily_usage.csv

# Last 30 days
ocmonitor export daily ~/.local/share/opencode/storage/message --days 30 --format json
```

#### 3. Weekly Reports Export

```bash
# Export weekly data
ocmonitor export weekly ~/.local/share/opencode/storage/message --format csv --output weekly_report.csv

# Last 12 weeks
ocmonitor export weekly ~/.local/share/opencode/storage/message --weeks 12 --format json
```

#### 4. Monthly Reports Export

```bash
# Export monthly analysis
ocmonitor export monthly ~/.local/share/opencode/storage/message --format csv --output monthly_analysis.csv

# Last 6 months
ocmonitor export monthly ~/.local/share/opencode/storage/message --months 6 --format json
```

#### 5. Model Usage Export

```bash
# Export model breakdown
ocmonitor export models ~/.local/share/opencode/storage/message --format csv --output model_usage.csv

# JSON format with metadata
ocmonitor export models ~/.local/share/opencode/storage/message --format json --include-metadata
```

#### 6. Project Usage Export

```bash
# Export project breakdown
ocmonitor export projects ~/.local/share/opencode/storage/message --format csv --output project_usage.csv

# JSON format with detailed metadata
ocmonitor export projects ~/.local/share/opencode/storage/message --format json --include-metadata

# Filter by date range
ocmonitor export projects ~/.local/share/opencode/storage/message --start-date 2024-01-01 --end-date 2024-01-31 --format csv
```

### Export Options

| Option | Description | Example |
|--------|-------------|---------|
| `--format` | Output format (`csv`, `json`) | `--format csv` |
| `--output` | Output filename | `--output report.csv` |
| `--limit` | Limit number of records | `--limit 100` |
| `--days` | Number of days to include | `--days 30` |
| `--weeks` | Number of weeks to include | `--weeks 12` |
| `--months` | Number of months to include | `--months 6` |
| `--include-metadata` | Include additional metadata | `--include-metadata` |
| `--include-raw-data` | Include raw session data | `--include-raw-data` |
| `--start-date` | Start date for filtering (YYYY-MM-DD) | `--start-date 2024-01-01` |
| `--end-date` | End date for filtering (YYYY-MM-DD) | `--end-date 2024-01-31` |
| `--timeframe` | Predefined timeframe filter | `--timeframe weekly` |

### CSV Export Example

```bash
ocmonitor export sessions ~/.local/share/opencode/storage/message --format csv --output sessions.csv
```

**Generated CSV Structure:**
```csv
session_id,date,start_time,end_time,duration_minutes,model,total_cost,input_tokens,output_tokens,cache_tokens
ses_20250118_143022,2025-01-18,14:30:22,14:53:37,23.25,claude-sonnet-4,2.45,15420,8340,2100
ses_20250118_120830,2025-01-18,12:08:30,12:53:38,45.13,claude-opus-4,4.32,18650,9240,1850
```

### JSON Export Example

```bash
ocmonitor export sessions ~/.local/share/opencode/storage/message --format json --output sessions.json --include-metadata
```

**Generated JSON Structure:**
```json
{
  "metadata": {
    "export_date": "2025-01-18T15:30:00Z",
    "tool_version": "1.0.0",
    "total_sessions": 25,
    "date_range": {
      "start": "2025-01-01",
      "end": "2025-01-18"
    }
  },
  "sessions": [
    {
      "session_id": "ses_20250118_143022",
      "date": "2025-01-18",
      "start_time": "14:30:22",
      "end_time": "14:53:37",
      "duration_minutes": 23.25,
      "model": "claude-sonnet-4",
      "total_cost": 2.45,
      "tokens": {
        "input": 15420,
        "output": 8340,
        "cache": 2100,
        "total": 25860
      },
      "cost_breakdown": {
        "input_cost": 0.46,
        "output_cost": 1.25,
        "cache_cost": 0.63,
        "total_cost": 2.45
      }
    }
  ]
}
```

### Automated Export Scripts

#### Daily Export Automation

Create a script for daily exports:

```bash
#!/bin/bash
# daily_export.sh

DATE=$(date +%Y%m%d)
EXPORT_DIR="./reports"

mkdir -p $EXPORT_DIR

# Export daily report
ocmonitor export daily \
  --format csv \
  --output "$EXPORT_DIR/daily_${DATE}.csv"

# Export sessions
ocmonitor export sessions \
  --format json \
  --output "$EXPORT_DIR/sessions_${DATE}.json" \
  --include-metadata

echo "Reports exported to $EXPORT_DIR/"
```

#### Weekly Report Generation

```bash
#!/bin/bash
# weekly_report.sh

WEEK=$(date +%Y_W%U)
ocmonitor export weekly \
  --format csv \
  --output "weekly_report_${WEEK}.csv" \
  --weeks 1

ocmonitor export models \
  --format csv \
  --output "model_usage_${WEEK}.csv"
```

---

## 🔧 Configuration Commands

### `ocmonitor config` Command Reference

The configuration command helps you manage and view your OpenCode Monitor settings.

### Viewing Configuration

#### Show All Configuration

```bash
# Display complete configuration
ocmonitor config show
```


**Text Output Example:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                                     ⚙️  Configuration                                        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

📁 Paths:
   Messages Directory: ~/.local/share/opencode/storage/message
   Export Directory: ./exports

🎨 UI Settings:
   Table Style: rich
   Progress Bars: enabled
   Colors: enabled
   Live Refresh: 5 seconds

📤 Export Settings:
   Default Format: csv
   Include Metadata: enabled
   Include Raw Data: disabled

🤖 Models:
   Configuration File: models.json
   Supported Models: 6

📊 Analytics:
   Default Timeframe: daily
   Recent Sessions Limit: 50
```

#### Show Current Configuration

```bash
# Show the full active configuration
ocmonitor config show
```

`ocmonitor config show` currently displays the full configuration. Section filtering options such as `--section` are not available in v1.0.3.

### Validating Configuration

There is currently no separate `ocmonitor config validate` command. Configuration is validated automatically whenever `ocmonitor` starts and loads `config.toml`.

#### Check That Configuration Loads

```bash
# Load and display the active configuration
ocmonitor config show
```

If the config file has invalid TOML syntax or unsupported values, `ocmonitor` will exit with an error before running the command.

#### Common Validation Checks

```bash
# Show the full configuration
ocmonitor config show
```

### Updating Configuration

#### Set Configuration Values

`ocmonitor config set` exists in the CLI help, but it is currently a placeholder and does not write changes yet.

For now, edit the configuration file directly:

```bash
# Edit the user config file directly
$EDITOR ~/.config/ocmonitor/config.toml

# Then verify the updated config loads correctly
ocmonitor config show
```

#### Reset Configuration

There is currently no `ocmonitor config reset` command.

To reset to defaults, remove or rename your custom config file and rerun `ocmonitor`:

```bash
# Back up your user config
mv ~/.config/ocmonitor/config.toml ~/.config/ocmonitor/config.toml.bak

# Confirm the app now loads with default settings
ocmonitor config show
```

If you use a project-local `config.toml` or `ocmonitor.toml`, remove or rename that file instead.

### Configuration File Locations

#### Find Configuration Files

There is currently no `ocmonitor config paths` command.

`ocmonitor` searches for configuration files in this order:

```text
~/.config/ocmonitor/config.toml
./config.toml
./ocmonitor.toml
packaged default config bundled with ocmonitor
```

**Example Output:**
```
📁 Configuration File Locations:

Primary Configuration:
   File: ~/.config/ocmonitor/config.toml
   Status: ✅ Found (recommended location)

Project Configuration:
   File: ./config.toml
   Status: ❌ Not found (optional)

Models Configuration:
   File: ./models.json
   Status: ✅ Found

Environment Overrides:
   OCMONITOR_MESSAGES_DIR: not set
   OCMONITOR_EXPORT_DIR: not set
```

### Environment Variable Override

You can override any configuration setting using environment variables:

```bash
# Override messages directory
export OCMONITOR_MESSAGES_DIR="/custom/path"

# Override export format
export OCMONITOR_EXPORT_FORMAT="json"

# Override UI settings
export OCMONITOR_UI_COLORS="false"
export OCMONITOR_UI_TABLE_STYLE="simple"

# Use the overrides
ocmonitor config show
```

---

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. Command Not Found: `ocmonitor`

**Problem:** Terminal shows `command not found: ocmonitor`

**Solutions:**

```bash
# Check if Python scripts directory is in PATH
echo $PATH | grep -o '[^:]*python[^:]*bin'

# Find Python user base
python3 -m site --user-base

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$(python3 -m site --user-base)/bin:$PATH"

# Reload shell
source ~/.bashrc  # or ~/.zshrc

# Alternative: Use full path
python3 /path/to/ocmonitor/run_ocmonitor.py --help

# Alternative: Reinstall in development mode
cd /path/to/ocmonitor
python3 -m pip install -e .
```

#### 2. Import Errors and Dependencies

**Problem:** Python import errors when running commands

**Solutions:**

**Option 1: Use pipx (Recommended for dependency issues)**
```bash
# Uninstall current version
pipx uninstall ocmonitor

# Reinstall with pipx (creates clean isolated environment)
cd /path/to/ocmonitor
pipx install .
```

**Option 2: Fix pip installation**
```bash
# Check Python version
python3 --version  # Should be 3.8+

# Reinstall dependencies
python3 -m pip install -r requirements.txt --force-reinstall

# Check for missing dependencies
python3 -c "import click, rich, pydantic, toml; print('All dependencies OK')"

# Install specific missing package
python3 -m pip install click rich pydantic toml

# Clear Python cache
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete
```

#### 3. Architecture Compatibility Issues

**Problem:** Architecture mismatch errors (arm64 vs x86_64)

**Solutions:**

```bash
# Check system architecture
uname -m

# For Apple Silicon Macs, use native Python
which python3
/opt/homebrew/bin/python3 --version

# Reinstall with correct architecture
python3 -m pip uninstall pydantic pydantic-core
python3 -m pip install pydantic pydantic-core --no-cache-dir

# Force reinstall all dependencies
python3 -m pip install -r requirements.txt --force-reinstall --no-cache-dir
```

#### 4. Messages Directory Not Found

**Problem:** `Messages directory not found` error

**Solutions:**

```bash
# Check if OpenCode is installed
which opencode

# Check default location
ls -la ~/.local/share/opencode/storage/message

# Find OpenCode data directory
find ~ -name "opencode" -type d 2>/dev/null

# Check OpenCode configuration
opencode config list 2>/dev/null | grep storage

# Set the messages directory by editing config.toml directly
$EDITOR ~/.config/ocmonitor/config.toml

# Verify the configuration loads correctly
ocmonitor config show
```

#### 5. JSON Parsing Errors

**Problem:** Errors when reading session files

**Solutions:**

```bash
# Check for corrupted session files
find ~/.local/share/opencode/storage/message -name "*.json" -exec python3 -m json.tool {} \; > /dev/null

# Find specific problematic files
find ~/.local/share/opencode/storage/message -name "*.json" -print0 | while IFS= read -r -d '' file; do
    python3 -m json.tool "$file" > /dev/null 2>&1 || echo "Invalid JSON: $file"
done

# Test with specific session
ocmonitor session ~/.local/share/opencode/storage/message/problematic_session

# Use verbose mode for debugging
ocmonitor sessions ~/.local/share/opencode/storage/message --verbose
```

#### 6. Permission Errors

**Problem:** Permission denied errors when accessing files

**Solutions:**

```bash
# Check file permissions
ls -la ~/.local/share/opencode/storage/message

# Fix permissions if needed
chmod -R 755 ~/.local/share/opencode/storage/message

# Check if export directory is writable
mkdir -p ./exports
touch ./exports/test.txt && rm ./exports/test.txt

# Use an alternative export directory by editing config.toml directly
$EDITOR ~/.config/ocmonitor/config.toml
```

#### 7. Model Not Recognized

**Problem:** "Unknown model" in reports

**Solutions:**

```bash
# Check which models are configured
ocmonitor config show

# View current models.json
cat models.json

# Find unrecognized model names in your data
grep -r "model.*:" ~/.local/share/opencode/storage/message | grep -v claude | grep -v grok | head -5

# Add missing model to models.json
# Edit models.json and add the new model configuration

# Verify the models configuration loads correctly
ocmonitor config show
```

#### 8. Export Failures

**Problem:** Export commands fail or produce empty files

**Solutions:**

```bash
# Test export with verbose output
ocmonitor export sessions --format csv --output test.csv --verbose

# Check export directory permissions
ls -la ./exports

# Try different export format
ocmonitor export sessions --format json --output test.json

# Test with limited data
ocmonitor export sessions --limit 5 --format csv

# Check disk space
df -h .
```

#### 9. SQLite Database Not Found (OpenCode v1.2.0+)

**Problem:** Sessions not found after upgrading OpenCode to v1.2.0+

**Solutions:**

```bash
# Check if SQLite database exists
ls -la ~/.local/share/opencode/opencode.db

# Verify data source detection
ocmonitor sessions --verbose

# Force SQLite mode
ocmonitor sessions --source sqlite

# Check for legacy files (pre-v1.2.0)
ls -la ~/.local/share/opencode/storage/message/

# Update the database location by editing config.toml directly
$EDITOR ~/.config/ocmonitor/config.toml
```

**Note:** OpenCode v1.2.0+ stores sessions in SQLite at `~/.local/share/opencode/opencode.db`. The tool automatically detects and prefers SQLite when available, falling back to legacy files only when SQLite is not found.

### Debug Mode

#### Enable Verbose Logging

```bash
# Run any command with verbose output
ocmonitor sessions ~/.local/share/opencode/storage/message --verbose

# Set debug environment variable
export OCMONITOR_DEBUG=1
ocmonitor sessions ~/.local/share/opencode/storage/message
```

#### Collect System Information

There is currently no `ocmonitor config system-info` command. When reporting issues, include the following command output instead:

```bash
ocmonitor --version
python3 --version
uname -a
ocmonitor config show
```

### Getting Help

#### Report Issues

When reporting issues, include:

1. **System Information:**
   ```bash
   ocmonitor --version
   python3 --version
   uname -a
   ```

2. **Error Messages:** Full error output with `--verbose` flag

3. **Configuration:**
   ```bash
   ocmonitor config show
   ```

4. **Steps to Reproduce:** Exact commands that cause the issue

#### Community Support

- 🐛 **GitHub Issues:** For bug reports and feature requests
- 💬 **Discussions:** For questions and community help
- 📚 **Documentation:** Check this guide and README files

---

## 📊 Using the --breakdown Flag

The `--breakdown` flag adds per-model token consumption and cost details to daily, weekly, and monthly reports.

```bash
# Show model breakdown in daily report
ocmonitor daily --breakdown

# Show model breakdown in weekly report
ocmonitor weekly --breakdown

# Show model breakdown in monthly report
ocmonitor monthly --breakdown
```

**Example Output:**
```
                             Daily Usage Breakdown                              
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┓
┃ Date / Model                            ┃ Sessions ┃ Interactions┃ Total Tokens┃    Cost ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━┩
│ 2024-01-13                              │        1 │          2 │     1,150 │ $0.0128 │
│   ↳ anthropic/claude-sonnet-4-20250514  │        1 │          2 │     1,150 │ $0.0128 │
│ 2024-01-14                              │        1 │          1 │     5,200 │ $0.0000 │
│   ↳ opencode/grok-code                  │        1 │          1 │     5,200 │ $0.0000 │
└─────────────────────────────────────────┴──────────┴────────────┴───────────┴─────────┘
```

**Features:**
- Model rows indented and styled distinctly
- Shows sessions, interactions, tokens, and cost per model
- Models sorted by cost (descending)
- Total row shows aggregate values

---

## 🚀 Advanced Tips

### Performance Optimization

#### Large Dataset Handling

```bash
# Process large datasets efficiently
ocmonitor sessions --limit 1000

# Use JSON format for faster processing
ocmonitor sessions --format json | jq '.sessions | length'

# Focus on recent data
ocmonitor daily --days 7
```

#### Batch Processing

```bash
# Export multiple reports with different filters
ocmonitor sessions --limit 100 --format csv --output recent_sessions.csv
ocmonitor weekly --weeks 4 --format json --output last_month.json
ocmonitor projects --format csv --output all_projects.csv
```

### Integration with Other Tools

#### Shell Scripts Integration

```bash
#!/bin/bash
# Monthly cost check script

COST=$(ocmonitor monthly --format json | jq '.summary.total_cost')
LIMIT=100.0

if (( $(echo "$COST > $LIMIT" | bc -l) )); then
    echo "⚠️ Monthly cost $COST exceeds limit $LIMIT"
    # Send notification, email, etc.
fi
```

#### Data Pipeline Integration

```bash
# Export for data analysis
ocmonitor export sessions \
    --format json \
    --include-raw-data \
    --output sessions.json

# Export project data for analysis
ocmonitor export projects \
    --format json \
    --include-metadata \
    --output projects.json

# Process with jq
cat sessions.json | jq '.sessions[] | select(.total_cost > 5.0)'
cat projects.json | jq '.projects[] | select(.cost > 10.0)'

# Import into database (example)
python3 scripts/import_to_db.py sessions.json
python3 scripts/import_projects_to_db.py projects.json
```

### Customization

#### Custom Export Scripts

Create custom export formats:

```python
#!/usr/bin/env python3
# custom_export.py

import json
import sys
from datetime import datetime

def custom_export(sessions_file):
    with open(sessions_file) as f:
        data = json.load(f)
    
    # Custom processing
    for session in data['sessions']:
        print(f"{session['date']},{session['model']},{session['total_cost']}")

if __name__ == "__main__":
    custom_export(sys.argv[1])
```

Usage:
```bash
ocmonitor export sessions --format json --output temp.json
python3 custom_export.py temp.json > custom_report.csv
```

#### Configuration Templates

Create configuration templates for different use cases:

```bash
# Development configuration
cp ~/.config/ocmonitor/config.toml ~/.config/ocmonitor/config.dev.toml
# Edit development settings
nano ~/.config/ocmonitor/config.dev.toml

# Production configuration  
cp ~/.config/ocmonitor/config.toml ~/.config/ocmonitor/config.prod.toml
# Edit production settings
nano ~/.config/ocmonitor/config.prod.toml

# Use specific configuration
OCMONITOR_CONFIG=~/.config/ocmonitor/config.dev.toml ocmonitor sessions
```

---

## 🧪 Testing

OpenCode Monitor uses pytest for testing. Tests are organized in `tests/`:
- `tests/unit/` - Unit tests for individual modules
- `tests/integration/` - CLI integration tests
- `tests/conftest.py` - Shared fixtures

### Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run with coverage
pytest --cov=ocmonitor
```

---

*This completes the comprehensive documentation for OpenCode Monitor. For additional help, please refer to the GitHub repository or file an issue for support.*
