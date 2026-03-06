# TUI Implementation Plan for OpenCode Monitor

## Context

The project has an approved TUI design document (`docs/plans/2026-03-04-tui-design.md`) specifying a Textual-based interactive terminal UI. Currently, all output is CLI-only via Rich tables. The TUI will become the default when running `ocmonitor` with no arguments, while existing CLI subcommands must remain unchanged.

This revision adds API compatibility details discovered during implementation review, so the plan aligns with current code behavior.

---

## Compatibility Requirements (Apply Before Building Screens)

1. **DataLoader path types**: initialize with `Path` objects, not raw strings (`DataLoader` later calls `.exists()`).
2. **Live hierarchy adapter**: `DataLoader.load_session_hierarchy()` returns `root_sessions` entries shaped as `{"session": ..., "sub_agents": ...}`; `WorkflowWrapper` expects `main_session/all_sessions/...`. Add an adapter helper.
3. **Timeframe filters**: `create_model_breakdown()` and `create_project_breakdown()` currently only apply `start_date/end_date`; `timeframe` is effectively metadata. Implement timeframe-to-date-range conversion in TUI.
4. **Top-level navigation model**: keep sidebar shell persistent (use `ContentSwitcher`/screen container), and reserve `push_screen()` for drill-down/modal flows.
5. **No-args CLI guards**: no-arg TUI launch should only occur in interactive mode; non-interactive environments should not try to open Textual.

---

## Phase 1: Foundation

### 1a. Dependencies and Packaging

**Modify `requirements.txt`**:
```txt
textual>=0.50.0
```

**Modify `setup.py`**:
- add `"textual>=0.50.0"` to `install_requires`
- ensure TUI packages are included (`find_packages()` already helps, but verify)
- include `"tui/*.tcss"` in `package_data["ocmonitor"]`

**Modify `pyproject.toml`**:
- add `textual` dependency
- include `ocmonitor.tui`, `ocmonitor.tui.widgets`, `ocmonitor.tui.screens` in setuptools package list
- include `"tui/*.tcss"` in package data

**Modify `MANIFEST.in`**:
- include TUI stylesheet(s) for sdist builds

### 1b. CLI Entry Point

**Modify `ocmonitor/cli.py`:**
- Change `@click.group()` to `@click.group(invoke_without_command=True)`
- After service initialization, if `ctx.invoked_subcommand is None`:
  - gate launch to interactive terminals (`stdin/stdout` TTY)
  - in non-interactive mode, show help and return gracefully
  - lazy-import and launch `OCMonitorApp`
  - catch `ImportError` and print actionable message if Textual is missing
- Add explicit `tui` subcommand (same launch logic)
- Pass `config`, `pricing_data`, `no_remote` from `ctx.obj` to app

### 1c. New Files - App Foundation

| File | Description |
|------|-------------|
| `ocmonitor/tui/__init__.py` | Package init |
| `ocmonitor/tui/widgets/__init__.py` | Package init |
| `ocmonitor/tui/screens/__init__.py` | Package init |
| `ocmonitor/tui/app.py` | `OCMonitorApp(App)` main entry |
| `ocmonitor/tui/widgets/sidebar.py` | Navigation sidebar |
| `ocmonitor/tui/widgets/breadcrumb.py` | Breadcrumb bar |
| `ocmonitor/tui/styles.tcss` | Textual stylesheet |

**`app.py` - `OCMonitorApp`:**
- Constructor accepts `config`, `pricing_data`, `no_remote`
- `on_mount()` initializes and stores:
  - `SessionAnalyzer(pricing_data)`
  - `SessionGrouper()`
  - `DataLoader(db_path=Path(config.paths.database_file), files_path=Path(config.paths.messages_dir))`
  - `ExportService(config.paths.export_dir)`
- `compose()` uses persistent shell: `Header` + horizontal container (`Sidebar` + content host) + `Footer`
- Use persistent top-level content switching (not full-screen push/pop for root screens)
- Keep `push_screen()/pop_screen()` for detail screens/modals only
- SCREENS map includes: sessions, daily, weekly, monthly, models, projects, live, config
- Default top-level screen: sessions
- Global bindings: `q`, `Esc/Backspace`, `e`, `t`, `?`, `1-8`
- Add app helpers:
  - `update_breadcrumb(path: list[str])`
  - `switch_top_level(screen_name: str)`
  - `adapt_hierarchy_to_workflows(hierarchy_dict) -> list[dict]`
  - `resolve_timeframe_dates(timeframe, start_date, end_date)`

**`sidebar.py` - `Sidebar`:**
- Groups: Analytics (Sessions, Daily, Weekly, Monthly), Breakdown (Models, Projects), Monitor (Live), System (Config)
- Each item emits `Sidebar.Navigate(screen_name)`
- Reactive active item highlight

**`breadcrumb.py` - `BreadcrumbBar`:**
- Reactive `path: list[str]` rendered as `" > ".join(path)`

**`styles.tcss`:**
- Sidebar fixed width, content flex area, header/footer docked
- Dark/light mode support via `self.dark`
- Map semantic color intent from `ui/theme.py` into Textual variables/classes
- Style DataTable, filter bar, breadcrumb, focus state, scrollbars

### Existing Code Reused
- `Config` + `config_manager` from `config.py`
- `SessionAnalyzer` from `services/session_analyzer.py`
- `SessionGrouper` from `services/session_grouper.py`
- `DataLoader` from `utils/data_loader.py`
- `DARK_THEME_STYLES` / `LIGHT_THEME_STYLES` from `ui/theme.py`

---

## Phase 2: Sessions Screen

**Create `ocmonitor/tui/screens/sessions.py`** with two classes.

### SessionsScreen (list view)
- Load data in worker/background task to avoid freezing UI
- Fetch flat sessions via `app.analyzer.analyze_all_sessions()`
- Grouped mode via `app.grouper.group_sessions(sessions)` (`SessionWorkflow` rows)
- Layout: BreadcrumbBar + FilterBar + DataTable + totals footer
- Columns: Started, Duration, Session, Model, Tokens, Cost, Agent
- Sort on header select
- `g` toggles grouped/flat
- Filters:
  - model: `analyzer.filter_sessions_by_model()`
  - project: list filter by `session.project_name`
  - limit: slice
- Enter on row opens `SessionDetailScreen`

### SessionDetailScreen
- Constructor takes `SessionData`
- Data sources:
  - `analyzer.get_session_statistics(session)`
  - `session.get_model_breakdown(app.pricing_data)`
  - `data_loader.load_tool_usage([session.session_id])`
- Note: file-based source may return empty tool usage (expected)
- Layout: info panel, quota/cost bar, interactions table, tool usage table, model breakdown
- Model/project interactions drill to related detail screens

**Create `ocmonitor/tui/widgets/filter_bar.py`:**
- Horizontal `Select`/input controls
- Emits `FilterChanged(filter_name, value)`

---

## Phase 3: Time Screens

### `ocmonitor/tui/screens/daily.py` - DailyScreen + DailyDetailScreen
- Data: `analyzer.create_daily_breakdown(sessions)`
- Columns: Date, Sessions, Interactions, Tokens, Cost, Models
- `d` toggles model breakdown
- Drill-down: day -> sessions list -> session detail

### `ocmonitor/tui/screens/weekly.py` - WeeklyScreen + WeeklyDetailScreen
- Data: `analyzer.create_weekly_breakdown(sessions, week_start_day)`
- Week-start filter from `WEEKDAY_MAP`
- Week label via `TimeUtils.format_week_range()`
- `d` toggles breakdown
- Drill-down: week -> daily -> session detail

### `ocmonitor/tui/screens/monthly.py` - MonthlyScreen + MonthlyDetailScreen
- Data: `analyzer.create_monthly_breakdown(sessions)`
- Columns: Month, Weeks, Sessions, Interactions, Tokens, Cost
- `d` toggles breakdown
- Drill-down: month -> week -> day -> session detail

---

## Phase 4: Models and Projects Screens

### `ocmonitor/tui/screens/models.py` - ModelsScreen + ModelDetailScreen
- Filters: timeframe (All/Daily/Weekly/Monthly), start date, end date
- Implement `resolve_timeframe_dates()` in app/screen layer:
  - convert timeframe to concrete date bounds
  - merge with explicit start/end if provided
  - pass resolved dates to analyzer
- Data: `analyzer.create_model_breakdown(sessions, timeframe, resolved_start, resolved_end)`
- Columns: Model, Sessions, Interactions, Input, Output, Total Tokens, Cost, Cost%, Speed (p50)
- Drill-down: model row -> ModelDetailScreen

**ModelDetailScreen:**
- `analyzer.get_model_detail(model_name)` for `ModelDetailStats`
- If source is not SQLite / no detail available, show clear empty-state message
- Show tokens, costs, tool usage, session list

### `ocmonitor/tui/screens/projects.py` - ProjectsScreen + ProjectDetailScreen
- Same timeframe/date filter behavior as Models
- Data: `analyzer.create_project_breakdown(sessions, timeframe, resolved_start, resolved_end)`
- Columns: Project, Sessions, Interactions, Tokens, Cost, Models Used, Last Activity
- Drill-down: project -> filtered sessions -> session detail

---

## Phase 5: Live Dashboard

**Create `ocmonitor/tui/screens/live.py`** - LiveScreen + WorkflowPickerModal

### LiveScreen
- `on_mount()`:
  - load hierarchy from `app.data_loader.load_session_hierarchy()`
  - adapt hierarchy to `WorkflowWrapper`-compatible dicts
  - select default workflow
- Auto-refresh: `self.set_interval(app.config.ui.live_refresh_interval, self._refresh_data)`
- `_refresh_data()`:
  - reload hierarchy
  - rebuild active workflow wrapper
  - refresh all widgets
- Keep timer handle; cancel on `on_unmount()` to avoid duplicate intervals
- Layout: active workflow header, token/cost/speed panels, model table, tool usage tables, sub-agent list, control hints

### Screen Keybindings
- `w`: open workflow picker modal
- `p`: pause/resume refresh timer
- `f`: fullscreen (hide/show sidebar shell)
- `+`/`-`: adjust refresh interval at runtime

### Reused Code
- `WorkflowWrapper` from `services/live_monitor.py`
- `DataLoader.load_session_hierarchy()`, `load_tool_usage()`, `load_tool_usage_by_model()`
- `compute_p50_output_rate()` from `utils/time_utils.py`

---

## Phase 6: Config Screen

**Create `ocmonitor/tui/screens/config.py`** - ConfigScreen (read-only)
- Data: `app.config`, `app.data_loader.get_source_info()`
- Show Paths, UI, Export, Models, source availability, and runtime flags (`no_remote`)
- No drill-down

---

## Phase 7: Polish

**Create `ocmonitor/tui/widgets/export_modal.py`:**
- `ModalScreen` with format select + Export/Cancel
- Every screen implements `get_export_data() -> tuple[report_type, report_data]`
- Use canonical report types expected by export service (`single_session`, `sessions`, `daily`, `weekly`, `monthly`, `models`, `projects`)
- Call `app.export_service.export_report_data(report_data, report_type, format_type)`
- Show result/error via `app.notify()`

**Help overlay:**
- Dismissible keybinding reference (`?`)

**Error handling:**
- Wrap data-loading actions in try/except
- Show user-facing errors via `app.notify(severity="error")`
- Keep stack traces behind verbose/debug mode only

**Performance safeguards:**
- Use workers/background tasks for heavy loads
- Debounce filter-driven refresh when needed

**Finalize `styles.tcss`:**
- focus styles, scrollbars, responsive widths
- progress classes mapped to success/warning/error thresholds

---

## File Summary

### New Files (17)
| File | Phase |
|------|-------|
| `ocmonitor/tui/__init__.py` | 1 |
| `ocmonitor/tui/app.py` | 1 |
| `ocmonitor/tui/styles.tcss` | 1 |
| `ocmonitor/tui/widgets/__init__.py` | 1 |
| `ocmonitor/tui/widgets/sidebar.py` | 1 |
| `ocmonitor/tui/widgets/breadcrumb.py` | 1 |
| `ocmonitor/tui/widgets/filter_bar.py` | 2 |
| `ocmonitor/tui/screens/__init__.py` | 1 |
| `ocmonitor/tui/screens/sessions.py` | 2 |
| `ocmonitor/tui/screens/daily.py` | 3 |
| `ocmonitor/tui/screens/weekly.py` | 3 |
| `ocmonitor/tui/screens/monthly.py` | 3 |
| `ocmonitor/tui/screens/models.py` | 4 |
| `ocmonitor/tui/screens/projects.py` | 4 |
| `ocmonitor/tui/screens/live.py` | 5 |
| `ocmonitor/tui/screens/config.py` | 6 |
| `ocmonitor/tui/widgets/export_modal.py` | 7 |

### Modified Files (5+)
| File | Phase | Change |
|------|-------|--------|
| `ocmonitor/cli.py` | 1 | `invoke_without_command=True`, guarded TUI launch, `tui` command |
| `requirements.txt` | 1 | add `textual>=0.50.0` |
| `setup.py` | 1 | add textual dependency and `.tcss` package data |
| `pyproject.toml` | 1 | include textual + TUI packages + package data |
| `MANIFEST.in` | 1 | include TUI styles for sdist |
| `tests/integration/test_cli.py` | 1 | add no-arg/tui launch behavior tests |
| `README.md` | 7 | update default no-arg behavior docs |

---

## Verification

After each phase:
1. `pip install -e .`
2. `ocmonitor` launches TUI in interactive terminal
3. `ocmonitor` in non-interactive context does not attempt TUI launch
4. `ocmonitor sessions`, `ocmonitor daily`, `ocmonitor weekly`, etc. still work
5. Sidebar navigation, drill-down, and back navigation work
6. Live screen refresh, picker, pause/resume, and fullscreen work

Automated checks:
```bash
pip install -e .
pytest tests/integration/test_cli.py -k "help or live or tui"
pytest tests/
```

End-to-end smoke test:
```bash
pip install -e .
ocmonitor          # launches TUI (interactive terminal)
ocmonitor tui      # launches TUI explicitly
ocmonitor sessions # CLI output still works
```
