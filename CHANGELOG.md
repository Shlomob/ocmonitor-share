# Changelog

All notable changes to OpenCode Monitor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.6] - Unreleased

### 🐛 Bug Fixes

- **Progress bar width is now fixed** — `TableFormatter.create_progress_bar`, `DashboardUI.create_progress_bar` / `create_compact_progress_bar`, and `utils.formatting.TableFormatter.create_progress_bar` clamp the fill computation to `[0, 100]`. Percentages above 100 previously widened the bar past its configured width and negative values shrank it, misaligning the Session Quota column. The `NNN.N%` label is unchanged and still prints the raw value

### ✨ Improvements

- **Over-quota sessions show their real percentage** — `SessionData.duration_percentage`, the live monitor session group, and the live dashboard's 5-hour time bars no longer cap at 100%. A session that ran 7.5 hours now displays `150.0%` with a full bar instead of flattening to `100.0%`. Note: `duration_percentage` is a computed field in JSON exports, so exported values can now exceed 100

## [1.0.5] - 2026-10-22

### 🌐 Provider-Aware Model Pricing

OpenCode stores both `providerID` and `modelID` per interaction. This release surfaces the provider throughout OCMonitor's output and aligns `models.json` keys with the same `provider/modelID` format, enabling accurate per-provider pricing.

#### Added
- **`provider_id` field** on `InteractionFile` — parsed from `providerID` in SQLite message JSON and file-based interactions (`Optional[str]`, default `None`)
- **`display_model` computed property** on `InteractionFile` — returns `provider/model` when provider is known, else bare model ID
- **`split_provider_model()` static helper** on `FileProcessor` — splits `display_model` on the first `/` for column rendering and is reused by `TableFormatter` and `ReportGenerator`
- **`_compact_models_display()` method** on `TableFormatter` — groups models by provider in the Daily Usage Breakdown Models column: single model → `provider/model`, multiple from same provider → `provider/{m1, m2}`, truncated to 3 groups with `(+N more)`
- **Separate Provider and Model columns** in all table builders (`models`, `daily`, `sessions`) and `report_generator.py` workflow table, replacing the former single `Model` column

#### Changed
- **`models.json` key format** migrated from bare `model-id` to `provider/model-id` (e.g., `anthropic/claude-sonnet-4-20250514`). All 42 existing entries updated with canonical provider IDs.
- **`models_used` and `get_model_breakdown`** now group by `display_model` (provider-qualified)
- **Prometheus `model` label** now emits `provider/model` values (e.g., `anthropic/claude-sonnet-4-20250514`)

#### Pricing Lookup Chain (5 steps, fully backward compatible)
Old bare-key `models.json` files continue to work without modification:
1. `provider_id/model_id` — exact provider+model match
2. `provider_id/normalize(model_id)` — provider + normalized model
3. `model_id` — bare exact match (legacy files)
4. `normalize(model_id)` — bare normalized
5. Scan `*/model_id` — any provider, model-only fallback

#### Files Modified
- `ocmonitor/models/session.py` — `provider_id`, `display_model`, 5-step lookup
- `ocmonitor/models/analytics.py` — `create_model_breakdown` uses `display_model`
- `ocmonitor/utils/sqlite_utils.py` — parses `providerID` from message JSON
- `ocmonitor/utils/file_utils.py` — parses `providerID`; provides `lookup_pricing()` (5-step) and `split_provider_model()` helpers
- `ocmonitor/ui/tables.py` — Provider+Model columns, `_split_provider_model()`, `_compact_models_display()`
- `ocmonitor/services/report_generator.py` — Provider+Model columns, `_split_provider_model()`
- `ocmonitor/models.json` — 42 entries in `provider/modelID` format

#### Fixed
- **Non-deterministic workflow model selection** — `report_generator.py` workflow summary now uses `sorted(set(...))` for stable ordering across runs
- **Provider/model split helper centralization** — moved split parsing to `FileProcessor.split_provider_model()` and updated all callers
- **Docstring coverage threshold** — increased docstring coverage to 92.4% (minimum 80%) by adding missing docstrings in touched source and test files


### 🗄️ OpenCode v2 Schema Support

OpenCode v2 moves sessions into `session_v2` and messages into `session_message`, with tool calls stored inline in each assistant message's `content` array. Earlier ocmonitor versions only read the legacy tables, which stop receiving data after the upgrade.

#### Added
- **Schema detection** in `SQLiteProcessor` — databases with a `session_v2` table are read using the v2 layout; v1 databases work unchanged
- **Legacy tables are merged in** when an upgraded database still has them: the v2 migration skips some older sessions' messages and rewrites `time.completed` on the ones it copies, so the original v1 rows are used where they exist and v2 adds only the newer messages. This keeps pre-upgrade history and output-speed stats intact
- v2 field mapping: role from the `type` column, model from `model.id`, provider from `model.providerID`, tool calls from `content[]` entries with `type: "tool"` and `name`
- Project path falls back to the session `directory` when messages carry no `path` (always the case in v2)

#### Fixed
- **`ocmonitor live` shows sessions from providers that report no token usage** instead of falling back to an older workflow; reports still exclude them
- **`--limit` counts sessions with usage data**, so `sessions --limit N` no longer returns nothing when the newest sessions have no token usage

### 💲 models.dev Remote Pricing Fixes

#### Fixed
- **Remote pricing parsed nothing**: `map_models_dev_to_local()` expected a `providers` wrapper and `cost.prompt`/`cost.completion`; it now reads the real API shape (providers at the top level, `cost.input`/`output`/`cache_read`/`cache_write`)
- **Default cache paths kept a literal `~`**: `remote_cache_path`, `user_file`, and `remote_rates_cache_path` defaults are now expanded
- **First fetch always failed**: the cache directory is created before the lock file, so the initial download no longer times out after 30 seconds

- **Provider-prefixed prices overwritten by aggregators**: a bare model ID containing `/` (e.g. an aggregator's `moonshotai/kimi-k3`) could replace the real provider's `provider/model` entry; prefixed entries now always win

#### Changed
- When several providers list the same bare model ID, a priced entry from a first-party provider now wins over the first one encountered
- `ocmonitor model` matches model IDs case-insensitively, so `GPT-5.5` and `gpt-5.5` are reported as one model

### ✨ Improvements

- Refresh bundled `models.json` from models.dev (2026-10-22): add 75 current models from OpenAI, Anthropic, Google, xAI, Meta, and open-weight labs (DeepSeek, Moonshot, Z.ai, Alibaba Qwen, MiniMax, Xiaomi, Mistral), correct 16 stale entries (e.g. `gpt-5`/`gpt-5.1`, `gpt-5-nano`, `gpt-5.4-pro` cache read, DeepSeek V4), and remove the mispriced `-free` entries, which charged paid prices for free models. Entries for retired models (GPT-5.x Codex, Claude Sonnet 4 / Opus 4.1 / Haiku 3.5, Gemini 3 Pro/Flash, Kimi K2/K2.5, `-extended` variants) are kept so historical sessions stay priced

### 📅 Interaction-Date Attribution

#### Changed
- **Daily, weekly, and monthly reports** count tokens and cost on the day each interaction happened, not the day its session started, so a session used across several days is split across those days
- **`--start-date` / `--end-date` filters** in the `models` and `projects` breakdowns include interactions that fall in the range, instead of whole sessions by start date

### 📚 Documentation

- Document OpenCode v2 support in README, DOCUMENTATION, and QUICK_START, including a troubleshooting entry for missing sessions after upgrading OpenCode to v2

### 🙏 Acknowledgements

Thanks to our contributors for this release:

- **[@mgoeppe](https://github.com/mgoeppe)** - Provider-aware model pricing and display ([#41](https://github.com/Shlomob/ocmonitor-share/pull/41)) and interaction-date attribution for time-based reports ([#42](https://github.com/Shlomob/ocmonitor-share/pull/42))
- **[@Nopparuj-an](https://github.com/Nopparuj-an)** - OpenCode v2 schema support and models.dev remote pricing fixes ([#51](https://github.com/Shlomob/ocmonitor-share/pull/51), continued in [#52](https://github.com/Shlomob/ocmonitor-share/pull/52))

## [1.0.4] - 2026-04-12

### ✨ Improvements

- Add `--recalculate` flag to `session`, `sessions`, `daily`, `weekly`, and `monthly` commands to recalculate costs using current pricing instead of stored values
- Add `--week`, `--month`, and `--year` bare flags for filtering recent periods (last 7 days, 30 days, 365 days respectively)
- Add `--month` and `--year` parameters with `last_n_days` support to `weekly` and `monthly` commands
- Add Cache Write and Cache Read columns to model breakdown tables
- Fix timeframe parameter handling for period filters

### 🙏 Acknowledgements

Thanks to our contributors for this release:

- **[@old-mikser](https://github.com/old-mikser)** - Added bare --week/--month/--year flags for recent period filtering ([#35](https://github.com/Shlomob/ocmonitor-share/pull/35))

## [1.0.3] - 2026-03-26

### 🐛 Bug Fixes

- Fix config file encoding on Windows by explicitly using UTF-8 for all file reads
- Fix config search order to check user config before packaged fallback
- Fix live dashboard to correctly aggregate workflow cost and token totals including sub-agents
- Fix workflow ordering to sort by latest parent message activity instead of session creation time
- Fix 10-workflow cap to apply after filtering unusable parent sessions, not before
- Fix SQL query to use `MAX(m.time_created)` for accurate parent activity detection
- Increase SQL LIMIT from 10 to 30 to reduce ACP session filtering issues
- Handle null/empty `sub_agents` lists gracefully in live dashboard

### ✨ Improvements

- Resolve runtime version from package metadata instead of hardcoded value
- Add `-h` as a short flag alias for `--help`
- Add detailed token breakdown (input/output/cache_read/cache_write) to daily report tables
- Rename `workflow_total` to `session_total` for consistent naming

### 🙏 Acknowledgements

Thanks to our contributors for this release:

- **[@bwendell](https://github.com/bwendell)** - Added `-h` short flag for help ([#33](https://github.com/Shlomob/ocmonitor-share/pull/33))
- **[@old-mikser](https://github.com/old-mikser)** - Fixed session picking edge cases, workflow aggregation, and SQL queries ([#30](https://github.com/Shlomob/ocmonitor-share/pull/30))

## [1.0.2] - 2026-03-14

### 🌍 Currency Conversion

Display costs in your local currency instead of USD with preset rates or live exchange rates.

#### Added
- **CurrencyConverter class** - Converts USD costs to display currency at render time
- **CurrencyConfig** - Configuration for code, symbol, rate, display format, decimals
- **Rate fetcher service** - Optional live rates from frankfurter.dev API
- **Exchange rate caching** - 24-hour TTL with stale cache fallback

#### Configuration
```toml
[currency]
code = "GBP"
symbol = "£"
rate = 0.79
display_format = "symbol_prefix"  # or "code_suffix"
remote_rates = false
```

#### Presets
- USD ($), GBP (£), EUR (€), CNY (¥), JPY (¥), INR (₹)
- JPY auto-applies 0 decimal places

#### Files Added
- `ocmonitor/utils/currency.py` - CurrencyConverter class
- `ocmonitor/services/rate_fetcher.py` - frankfurter.dev integration

#### Files Modified
- `ocmonitor/config.py` - Added CurrencyConfig
- `ocmonitor/config.toml` - Added [currency] section
- `ocmonitor/cli.py` - Wired converter into services
- `ocmonitor/ui/tables.py` - format_currency delegates to converter
- `ocmonitor/services/report_generator.py` - Replaced 12 hardcoded `$` sites
- `ocmonitor/ui/dashboard.py` - Replaced 15 hardcoded `$` sites
- `ocmonitor/services/export_service.py` - Converted costs + currency metadata

## [1.0.1] - 2026-03-13

### 📊 Prometheus Metrics Endpoint

New `ocmonitor metrics` command starts a lightweight HTTP server exposing session analytics in Prometheus exposition format for Grafana integration.

#### Added
- **`metrics` command** - Starts Prometheus metrics server on configurable port (default: 9090)
- **OCMonitorCollector class** - Custom collector pattern yielding fresh session data on each scrape
- **MetricsServer service** - HTTP server with graceful shutdown on Ctrl+C
- **MetricsConfig** - Configuration section for host/port settings

#### Metrics Exposed
- `ocmonitor_tokens_input_total{model}` - Total input tokens per model
- `ocmonitor_tokens_output_total{model}` - Total output tokens per model
- `ocmonitor_tokens_cache_read_total{model}` - Total cache read tokens per model
- `ocmonitor_tokens_cache_write_total{model}` - Total cache write tokens per model
- `ocmonitor_cost_dollars_total{model}` - Total cost per model
- `ocmonitor_sessions_total{model}` - Total sessions per model
- `ocmonitor_interactions_total{model}` - Total interactions per model
- `ocmonitor_output_rate_tokens_per_second{model}` - P50 output rate per model
- `ocmonitor_session_duration_hours_total` - Total session duration across all models
- `ocmonitor_sessions_by_project{project}` - Sessions grouped by project

#### Usage
```bash
# Start metrics server (default port 9090)
ocmonitor metrics

# Custom port
ocmonitor metrics --port 8080

# Custom host
ocmonitor metrics --host 127.0.0.1 --port 9090

# Scrape metrics
curl http://localhost:9090/metrics
```

#### Configuration
```toml
[metrics]
port = 9090
host = "0.0.0.0"
```

#### Files Modified
- `ocmonitor/services/metrics_server.py` - Created metrics server with Custom Collector pattern
- `ocmonitor/cli.py` - Added `metrics` command
- `ocmonitor/config.py` - Added `MetricsConfig` class
- `ocmonitor/config.toml` - Added `[metrics]` section
- `requirements.txt`, `setup.py`, `pyproject.toml` - Added `prometheus_client>=0.17.0` dependency

#### Dependencies
- `prometheus_client>=0.17.0` - Required for metrics endpoint
- Install with: `pip install "ocmonitor[metrics]"` or `pip install prometheus_client>=0.17.0`

#### Tests
- 8 unit tests for OCMonitorCollector (empty sessions, per-model labels, error handling)
- 3 unit tests for MetricsServer (startup, registration, graceful shutdown)
- 3 integration tests for CLI command (help, port configuration, error handling)

## [0.9.4] - 2026-03-03

### 🔍 Model Detail Command

New `ocmonitor model <name>` command for drilling into a single AI model with rich statistics.

#### Added
- **`model` command** - Detailed breakdown for a single model, fuzzy-matched by name
- **ModelDetailStats Model** - Pydantic model with first/last used, sessions, days used, interactions, token breakdown, costs, output speed, and tool stats
- **Fuzzy Name Matching** - Substring match against all model names in the database
  - 0 matches: shows "No model found" + full list of available models
  - >1 matches: lists candidates with "Did you mean one of these?"
  - Exact match wins even when other substring matches exist
- **SQLite Queries** - Two new classmethods on `SQLiteProcessor`:
  - `find_matching_models(query)` - fuzzy substring search
  - `get_model_detail_stats(model_name, pricing_data)` - aggregate stats + output rates + tool stats

#### Files Modified
- `ocmonitor/models/analytics.py` - Added `ModelDetailStats` class
- `ocmonitor/utils/sqlite_utils.py` - Added `find_matching_models()` and `get_model_detail_stats()`
- `ocmonitor/utils/data_loader.py` - Added `find_matching_models()` and `get_model_detail()` delegation methods
- `ocmonitor/services/session_analyzer.py` - Added `find_matching_models()` and `get_model_detail()` methods
- `ocmonitor/services/report_generator.py` - Added `generate_model_detail_report()`, `_display_model_detail()`, JSON/CSV formatters
- `ocmonitor/ui/tables.py` - Added `create_model_detail_panel()` and `create_model_tool_table()`
- `ocmonitor/cli.py` - Added `model` command

#### Features
- 📋 **Key-Value Panel** - First Used, Last Used, Sessions, Days Used, Interactions, Input/Output/Cache tokens, Total Cost, Avg/Day, Avg/Session, Output Speed (p50)
- 🔧 **Tool Usage Table** - Per-tool Calls, Success, Failed, and color-coded Success Rate (green ≥90%, yellow ≥70%, red <70%)
- 📊 **Tool Summary** - Total calls, successes, failures, overall success rate
- 📤 **JSON/CSV Export** - Full stats available via `-f json` or `-f csv`

#### Usage
```bash
# Exact or fuzzy match
ocmonitor model claude-sonnet-4-5
ocmonitor model sonnet        # lists all sonnet variants
ocmonitor model nonexistent   # shows available models

# JSON output
ocmonitor model claude-opus-4-5 -f json
```

### 🎯 Live Workflow Picker & Session Pinning

Interactive workflow selection and switching during live monitoring.

#### Added
- **`--pick` flag** - Interactive picker to select workflow before starting live monitor
- **`--session-id` flag** - Pin live monitor to specific workflow/session ID
- **`--interactive-switch` flag** - Enable keyboard controls during live monitoring
- **Live switching controls** - Press n/p for next/previous, l to list, 1-9 to jump, q to quit

#### Usage
```bash
ocmonitor live --pick                    # Pick workflow, enable switching
ocmonitor live --session-id ses_abc123   # Pin to specific session
ocmonitor live --interactive-switch      # Enable keyboard controls
```

#### Files Modified
- `ocmonitor/cli.py` - Added `--pick`, `--session-id`, `--interactive-switch` options
- `ocmonitor/services/live_monitor.py` - Added picker, terminal input handling, workflow switching
- `ocmonitor/ui/dashboard.py` - Added controls panel to dashboard layout

#### Tests
- 197 unit tests for picker, command handling, session resolution
- 2 integration tests for CLI flag precedence

## [0.9.3] - 2026-02-20

### 🔧 Tool Usage Tracking

Real-time tool success/failure metrics in the live dashboard.

#### Added
- **Tool Usage Panel** - Shows success rates for tools (bash, read, edit, etc.) in live dashboard
- **ToolUsageStats Model** - Tracks tool_name, total_calls, success_count, failure_count, success_rate
- **SQLite Tool Aggregation** - Queries `part` table for tool entries with terminal statuses

#### Files Added
- `ocmonitor/models/tool_usage.py` - Tool usage statistics models
- `tests/unit/test_sqlite_tool_usage.py` - Unit tests for tool aggregation

#### Files Modified
- `ocmonitor/utils/sqlite_utils.py` - Added `load_tool_usage_for_sessions()` method
- `ocmonitor/utils/data_loader.py` - Added `load_tool_usage()` method
- `ocmonitor/services/live_monitor.py` - Integrated tool stats into dashboard generation
- `ocmonitor/ui/dashboard.py` - Added Tools panel, modified layout (Models + Tools side-by-side)

#### Features
- 📊 **Success Rate Tracking** - Shows completed vs error counts per tool
- 🎨 **Color-Coded Progress Bars** - Green (≥90%), yellow (70-89%), red (<70%)
- 📋 **Top 6 Tools** - Shows most-used tools by call count
- 🚫 **Status Filtering** - Only counts `completed` and `error` statuses; excludes `running`

#### Layout Change
- Bottom section changed from full-width Models panel to side-by-side: `Models (60%)` | `Tools (40%)`

#### Tests
- 9 unit tests for tool usage aggregation and model

## [0.9.2] - 2026-02-17

### 🌐 Remote Pricing Fallback

Optional integration with [models.dev](https://models.dev) for automatic model pricing updates, filling gaps not covered by local pricing files.

#### Added
- **Remote Pricing Fallback** - Fetch model pricing from `https://models.dev/api.json`
- **Shared Cache** - Cross-project cache at `~/.cache/ocmonitor/models_dev_api.json`
- **User Override File** - `~/.config/ocmonitor/models.json` with highest priority
- **`--no-remote` Flag** - Disable remote fetch for a single command
- **Stale Cache Fallback** - Use expired cache when network unavailable

#### Files Added
- `ocmonitor/services/price_fetcher.py` - Remote fetcher with caching and locking

#### Configuration
```toml
[models]
remote_fallback = false           # Opt-in (default: disabled)
remote_url = "https://models.dev/api.json"
remote_timeout_seconds = 8
remote_cache_ttl_hours = 24
remote_cache_path = "~/.cache/ocmonitor/models_dev_api.json"
user_file = "~/.config/ocmonitor/models.json"
allow_stale_cache_on_error = true
```

#### Pricing Precedence (highest → lowest)
1. User override file (`~/.config/ocmonitor/models.json`)
2. Project/local `models.json`
3. models.dev remote fallback (fill-only, never overwrites)

#### Features
- 🔒 **Atomic Cache Writes** - Safe concurrent access with file locking
- 📦 **Dual Model Keys** - Both `model-name` and `provider/model-name` supported
- 🔄 **TTL-based Caching** - 24-hour default, configurable
- 🛡️ **Graceful Degradation** - CLI works offline, uses stale cache if available
- ⚡ **Field-level Merge** - Remote only fills missing fields, never overwrites

#### Usage
```bash
# Enable in config, then use normally
ocmonitor sessions

# Force local-only pricing
ocmonitor --no-remote sessions
```

#### Tests
- 25 unit tests for price fetcher (cache, locking, mapping)
- 8 unit tests for config merge logic

## [0.9.1] - 2026-02-14

### ✨ SQLite Database Support

OpenCode v1.2.0+ migrated session storage from flat JSON files to SQLite. This release adds full support for the new database format while maintaining backwards compatibility.

#### Added
- **SQLite Database Support** - Read sessions from `~/.local/share/opencode/opencode.db`
- **Dual Storage Architecture** - Automatically prefers SQLite when available, falls back to legacy files
- **Hierarchical Session Display** - Parent sessions with sub-agents shown in tree view
- **Live Workflow Monitoring** - Tracks only current workflow (main + sub-agents) from SQLite
- **DataLoader Abstraction** - Unified interface with automatic source detection

#### Files Added
- `ocmonitor/utils/sqlite_utils.py` - SQLite database access layer
- `ocmonitor/utils/data_loader.py` - Unified data loading with automatic fallback

#### Modified Commands
```bash
# Auto-detect SQLite or files (default)
ocmonitor live
ocmonitor sessions

# Force specific source
ocmonitor live --source sqlite
ocmonitor live --source files
ocmonitor sessions --source sqlite
```

#### Features
- 🗄️ **SQLite Integration** - Reads from `opencode.db` session/message tables
- 🌳 **Hierarchical View** - Parent sessions grouped with sub-agents
- 🔄 **Auto Fallback** - Automatically uses legacy files if SQLite unavailable
- 📊 **Workflow Tracking** - Live dashboard monitors current workflow only
- 🔍 **Source Detection** - Verbose mode shows which data source is active

#### Database Schema Support
- **session table** → SessionData with parent_id relationships
- **message table** → InteractionFile (parsed from JSON data column)
- **project table** → Project paths via JOIN

#### Technical Changes
- SessionData model extended with `parent_id`, `is_sub_agent`, `source` fields
- LiveMonitor adds SQLite workflow monitoring methods
- DataLoader provides `sqlite_available`, `files_available` properties
- Backwards compatible with OpenCode < v1.2.0

## [0.9.0] - 2026-02-05

### 🎉 Initial Release

#### Added
- **Core CLI Application** - Complete command-line interface with Click framework
- **Rich Terminal UI** - Beautiful tables, progress bars, and colored output
- **Comprehensive Analytics** - Daily, weekly, monthly, and model-based breakdowns
- **Real-time Monitoring** - Live dashboard for active session monitoring
- **Data Export** - CSV and JSON export functionality with metadata
- **Multi-model Support** - Support for 6 AI models including Claude, Grok, Qwen, and Z-AI
- **Professional Documentation** - Complete setup guides and user documentation

#### Features
- 📊 **Session Analysis** - Analyze individual or batch sessions
- 💰 **Cost Tracking** - Accurate cost calculations with model-specific pricing
- 📈 **Usage Analytics** - Token usage, context utilization, and performance metrics
- 🎨 **Rich UI Components** - Color-coded tables with progress indicators
- ⚙️ **TOML Configuration** - User-friendly configuration management
- 🔄 **Live Dashboard** - Real-time session monitoring with auto-refresh
- 📤 **Export Capabilities** - Professional CSV and JSON exports

#### Supported Commands
```bash
ocmonitor config show      # Display configuration
ocmonitor session <path>   # Analyze single session
ocmonitor sessions <path>  # Analyze all sessions  
ocmonitor daily <path>     # Daily usage breakdown
ocmonitor weekly <path>    # Weekly usage breakdown
ocmonitor monthly <path>   # Monthly usage breakdown
ocmonitor models <path>    # Model usage analytics
ocmonitor live <path>      # Real-time monitoring
ocmonitor export <type>    # Data export functionality
```

#### Supported AI Models
- **Claude Sonnet 4** (2025-05-14) - $3/$15 per 1M tokens, 200k context
- **Claude Opus 4** - $15/$75 per 1M tokens, 200k context  
- **Claude Opus 4.1** - $15/$75 per 1M tokens, 200k context
- **Grok Code** - FREE, 256k context
- **Qwen3 Coder** (qwen/qwen3-coder) - FREE, 256k context
- **Z-AI GLM 4.5 Air** (z-ai/glm-4.5-air) - FREE, 128k context

#### Technical Improvements
- **Modular Architecture** - Clean separation of concerns with services, models, and UI
- **Error Handling** - Comprehensive error handling with user-friendly messages
- **Type Safety** - Full type hints and Pydantic models for data validation
- **Performance** - Memory-efficient processing of large session datasets
- **Extensibility** - Easy addition of new models and features

### 🛠️ Development Infrastructure

#### Added
- **Automated Installation** - `install.sh` script for easy setup
- **Comprehensive Testing** - Manual test suites and validation scripts
- **Documentation** - README, Quick Start, Manual Test Guide
- **Configuration Management** - TOML config with JSON model pricing
- **PATH Management** - Automatic PATH configuration handling

### 🐛 Bug Fixes

#### Fixed
- **JSON Serialization** - Fixed Decimal serialization for JSON exports
- **Model Name Parsing** - Proper handling of fully qualified model names (e.g., `qwen/qwen3-coder`)
- **Zero-token Filtering** - Filtered out empty interactions that caused confusion
- **Export Data Structure** - Fixed CLI export command data structure issues
- **Import Path Resolution** - Resolved Python module path issues
- **Installation Issues** - Created comprehensive installation guides and PATH configuration

### 📚 Documentation

#### Added
- **README.md** - Complete project overview and usage instructions
- **QUICK_START.md** - Fast setup and common usage patterns
- **MANUAL_TEST_GUIDE.md** - Comprehensive testing procedures
- **PROJECT_SUMMARY.md** - Detailed project documentation and achievements
- **Installation Guides** - Multiple installation methods with troubleshooting

### 🧪 Testing

#### Added
- **Basic Functionality Tests** - Core feature validation
- **Import Validation** - Module import and dependency checks
- **CLI Command Tests** - All command-line interfaces tested
- **Real Data Testing** - Validation with actual OpenCode session data
- **Error Scenario Testing** - Edge case and error handling validation

---

## Version History Summary

- **v1.0.4** - Added --recalculate flag and bare --week/--month/--year flags for recent period filtering; Cache Write/Read columns in model breakdown
- **v1.0.3** - Bug fixes for config encoding, workflow aggregation, and SQL queries; version metadata resolution
- **v1.0.2** - Currency conversion (USD, GBP, EUR, JPY, CNY, INR) with live rates
- **v1.0.1** - Prometheus `/metrics` endpoint for Grafana integration
- **v0.9.4** - Model detail command with fuzzy matching; live workflow picker and session pinning
- **v0.9.3** - Tool usage tracking in live dashboard
- **v0.9.2** - Remote pricing fallback from models.dev
- **v0.9.1** - SQLite database support for OpenCode v1.2.0+
- **v0.9.0** - Pre-release version for community feedback and testing before stable v1.0.0
- **Pre-release** - Development phases transforming basic scripts into professional CLI tool

## Migration from Legacy Scripts

This release replaces the original three Python scripts:
- `session_summarizer.py` → `ocmonitor sessions`
- `token_summarizer.py` → `ocmonitor models` 
- `live_dashboard.py` → `ocmonitor live`

The new unified CLI provides all original functionality plus significant enhancements:
- Beautiful Rich terminal interface
- Comprehensive analytics and breakdowns
- Professional export capabilities  
- Real-time monitoring dashboard
- Robust error handling and validation
- Easy installation and configuration

---

*For detailed information about each feature, see the [README.md](README.md) and [documentation](QUICK_START.md).*
