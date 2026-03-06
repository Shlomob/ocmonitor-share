# TUI Design for OpenCode Monitor

**Date:** 2026-03-04
**Status:** Approved

## Goal

Add an interactive Text User Interface (TUI) to ocmonitor for browsing and drilling into sessions, models, and projects without re-running CLI commands. The TUI becomes the default when running `ocmonitor` with no arguments. All existing CLI subcommands remain unchanged.

## Decisions

- **Framework:** Textual (by Textualize, same team as Rich)
- **Navigation:** Sidebar + content area layout
- **Drill-down:** In-place replace with breadcrumb trail and screen stack (push/pop)
- **Architecture:** Screen-per-view (each sidebar item is a separate Textual Screen)
- **Entry point:** `ocmonitor` (no args) launches TUI; `ocmonitor sessions`, `ocmonitor daily`, etc. still use CLI
- **Live dashboard:** Integrated as a sidebar view, with `[f]` fullscreen option

## Layout

```
+--────────────────────────────────────────────────────────────────+
|  OpenCode Monitor                                Dark    v0.x   |
+─────────────+────────────────────────────────────────────────────+
|             | Sessions > Session #abc123                        |
|  Sessions   |────────────────────────────────────────────────────|
|  Daily      |                                                    |
|  Weekly     |  (Content area - changes per screen)               |
|  Monthly    |                                                    |
|  ─────────  |  DataTable / Panels / Progress Bars / Dashboard    |
|  Models     |                                                    |
|  Projects   |                                                    |
|  ─────────  |                                                    |
|  Live       |                                                    |
|  ─────────  |                                                    |
|  Config     |                                                    |
+─────────────+────────────────────────────────────────────────────+
| [q] Quit  [/] Search  [e] Export  [b] Back      Total: $47.23  |
+──────────────────────────────────────────────────────────────────+
```

**Sidebar groups:** Analytics (Sessions, Daily, Weekly, Monthly), Breakdown (Models, Projects), Monitor (Live), System (Config).

## Screens & Drill-down Map

```
Sessions Screen (home)
  └── row click → Session Detail Screen
                    ├── model click → Model Detail Screen
                    └── project click → Project Detail Screen

Daily Screen
  └── date click → Daily Detail (sessions for that day)
                     └── row click → Session Detail

Weekly Screen
  └── week click → Weekly Detail (daily breakdown for that week)
                     └── day click → Daily Detail

Monthly Screen
  └── month click → Monthly Detail (weekly breakdown)
                      └── week click → Weekly Detail

Models Screen
  └── model click → Model Detail (sessions using that model)
                      └── session click → Session Detail

Projects Screen
  └── project click → Project Detail (sessions for that project)
                        └── session click → Session Detail

Live Screen (auto-refreshing)
  ├── workflow picker via [w] key
  ├── [f] fullscreen mode
  └── session click → Session Detail

Config Screen (read-only)
```

**Navigation:** Enter/click drills in. Esc/Backspace goes back. Sidebar click goes to top-level screen.

## Screen Wireframes

### Sessions Screen

```
Sessions > All Sessions
────────────────────────────────────────────────────────────────
 Filter: [All Models v]  [All Projects v]  [Last 50 v]  [g] Group

 Started    Duration  Session                Model        Tokens   Cost    Agent
 10:30 AM   1h 23m    Fix login bug          sonnet-4-5    45.2k   $1.23    +2
 08:15 AM   45m       Add auth middleware    opus-4        23.1k   $2.45
 Yesterday  2h 10m    Refactor DB layer     sonnet-4-5   112.4k   $4.10    +1

                                                  Total: 180.7k   $7.78
```

Sortable columns, filter dropdowns, `[g]` toggles workflow grouping.

### Session Detail Screen

```
Sessions > Fix login bug
────────────────────────────────────────────────────────────────
 Session Info
   Project: ocmonitor    Started: 10:30 AM    Interactions: 12
   Model: claude-sonnet-4-5    Duration: 1h 23m (27%)

 Cost: $1.23 / $6.00  ████████████░░░░░░░░░░░░░░ 20%

 Interactions:
   #   Time     Input    Output   Cache     Cost
   1   10:30am   2,340      890    1,120    $0.12
   2   10:34am   4,120    1,230    2,340    $0.18
   ...

 Tool Usage:
   bash   298 calls   ████████████████████░ 96%
   edit   412 calls   ███████████████████░░ 94%
   read   620 calls   ████████████████████░ 96%
```

### Live Dashboard Screen

```
Live > ocmonitor (auto-refresh: 3s)
────────────────────────────────────────────────────────────────
 Active Session
   "Fix login bug"                          Updated: 10:45:32
   Project: ocmonitor   Model: claude-sonnet-4-5
   Duration: 0h 23m  ██░░░░░░░░░░░░░░░░░░░░░░░ 8%
   Speed: 62.4 tok/s

 Tokens              Cost
   In     Out          $1.23 / $6.00
   2.3k   890          ████████████░░░░░░░░ 20%
   45.2k  12.1k

 Model      Input    Output   Cost
 sonnet-4-5  42.1k    11.2k   $1.10
 haiku-3.5    3.1k     0.9k   $0.13

 Tool     Calls  Success  Failed  Rate
 bash       298      285      13   96%
 edit       412      389      23   94%
 read       620      598      22   96%

 Sub-agents: explore(ses_def456), ...

 [w] Switch Workflow  [p] Pause/Resume  [f] Fullscreen
```

## CLI-to-TUI Feature Parity

| CLI Flag/Feature | TUI Equivalent |
|---|---|
| `--no-group` | `[g]` toggle on Sessions screen |
| `--limit N` | Dropdown: Last 10/25/50/All |
| `--breakdown` | `[d]` toggle on Daily/Weekly/Monthly |
| `--start-day` (weekly) | Dropdown on Weekly screen |
| `--timeframe` (models/projects) | Dropdown filter |
| `--start-date` / `--end-date` | Text input fields on Models/Projects |
| `--interval N` (live) | `[+]`/`[-]` keys or Config |
| `--pick` (live) | `[w]` workflow picker modal |
| `--session-id` (live) | Via workflow picker or sessions list |
| `--interactive-switch` (live) | Always available via `[w]` |
| `export <type> --format` | `[e]` key → export modal from any screen |
| `config show` | Config screen in sidebar |
| `--theme dark\|light` | `[t]` toggle or header icon |
| `--verbose` | `[v]` toggle |
| `--no-remote` | Status indicator in Config screen |
| `--source` | Selectable in Config screen |
| Tool usage panel (live) | Always shown in Live screen |
| Sub-agent sessions (live) | Always shown when available |
| Output rate (live) | Shown in Live screen tokens area |

## Global Keybindings

| Key | Action |
|---|---|
| `q` | Quit |
| `Esc` / `Backspace` | Go back one level |
| `/` | Focus search/filter |
| `e` | Export current view |
| `t` | Toggle dark/light theme |
| `f` | Fullscreen mode (Live screen only) |
| `g` | Toggle workflow grouping (Sessions) |
| `d` | Toggle model breakdown (Daily/Weekly/Monthly) |
| `w` | Switch workflow (Live screen) |
| `p` | Pause/resume auto-refresh (Live screen) |
| `+` / `-` | Adjust refresh interval (Live screen) |
| `1`-`7` | Jump to sidebar item by position |
| `?` | Show help overlay |

## Technical Architecture

### File Structure

```
ocmonitor/ocmonitor/
├── tui/
│   ├── __init__.py
│   ├── app.py                    # OCMonitorApp(App) - main entry
│   ├── styles.tcss               # Textual CSS stylesheet
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── sidebar.py            # Navigation sidebar
│   │   ├── breadcrumb.py         # Breadcrumb navigation bar
│   │   ├── filter_bar.py         # Dropdown filters for tables
│   │   └── export_modal.py       # Export format picker
│   └── screens/
│       ├── __init__.py
│       ├── sessions.py           # Sessions list + detail
│       ├── daily.py              # Daily breakdown + detail
│       ├── weekly.py             # Weekly breakdown + detail
│       ├── monthly.py            # Monthly breakdown + detail
│       ├── models.py             # Models list + detail
│       ├── projects.py           # Projects list + detail
│       ├── live.py               # Live dashboard (normal + fullscreen)
│       └── config.py             # Config display
```

### Data Flow

```
App startup → ConfigManager → DataLoader (SQLite/files) → pricing data → Mount app

Screen activation → Screen.on_mount() → SessionAnalyzer / TimeframeAnalyzer → DataTable

Drill-down → push_screen(DetailScreen(data)) → render detail → Esc → pop_screen()

Live dashboard → set_interval() polling → DataLoader.load() → reactive widget updates
```

### Integration

The TUI only replaces the rendering layer. All existing code is reused:
- `models/` - Pydantic data models (unchanged)
- `services/session_analyzer.py` - Session analysis (unchanged)
- `services/session_grouper.py` - Workflow grouping (unchanged)
- `models/analytics.py` - TimeframeAnalyzer (unchanged)
- `utils/data_loader.py` - Data loading (unchanged)
- `config.py` - Configuration (unchanged)

### Entry Point

```python
# cli.py modification
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        from ocmonitor.tui.app import OCMonitorApp
        app = OCMonitorApp()
        app.run()

@cli.command()
def tui():
    """Launch the interactive TUI."""
    from ocmonitor.tui.app import OCMonitorApp
    app = OCMonitorApp()
    app.run()
```

### New Dependency

```
textual>=0.50.0
```

## Implementation Order

1. **Foundation:** `tui/app.py`, sidebar widget, basic screen switching, styles.tcss
2. **Sessions screen:** DataTable with existing session data, sorting, filters
3. **Session detail screen:** Drill-down from sessions, interaction table, tool usage
4. **Time screens:** Daily, Weekly, Monthly with breakdown toggle
5. **Models & Projects screens:** List + detail with date filters
6. **Live dashboard:** Integrated view with auto-refresh, fullscreen mode, workflow picker
7. **Config screen:** Read-only config display
8. **Polish:** Export modal, theme toggle, help overlay, keybindings, error handling
