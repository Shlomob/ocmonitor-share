"""Theme management for OpenCode Monitor."""

from rich.theme import Theme

# Semantic style definitions for the Dark Theme (Default)
# These match the original hardcoded colors of the application.
DARK_THEME_STYLES = {
    # Dashboard components
    "dashboard.header": "bold blue",
    "dashboard.title": "bold magenta",
    "dashboard.border": "dim blue",
    "dashboard.info": "bold yellow",
    "dashboard.project": "bold cyan",
    "dashboard.session": "bold white",
    
    # Metrics and Data
    "metric.label": "dim white",
    "metric.value": "bold white",
    "metric.important": "bold cyan",
    "metric.tokens": "bold cyan",
    "metric.cost": "bold white",
    
    # Flash highlight for real-time value changes
    "metric.flash": "bold yellow",           # 通用数值变化 - 黄色醒目
    "metric.flash.cost": "bold bright_green", # 成本变化 - 绿色醒目
    "metric.flash.tokens": "bold bright_green", # Token 变化 - 绿色醒目
    
    # Status and Indicators
    "status.success": "green",
    "status.warning": "yellow",
    "status.error": "red",
    "status.info": "cyan",
    "status.active": "green",
    "status.idle": "dim white",
    
    # Tables
    "table.header": "bold blue",
    "table.title": "bold magenta",
    "table.row.main": "white",
    "table.row.dim": "dim white",
    "table.row.project": "dim cyan",
    "table.row.model": "yellow",
    "table.row.time": "cyan",
    "table.row.cost": "red",
    "table.row.tokens": "bold blue",
    "table.footer": "bold white",
}

# Semantic style definitions for the Light Theme
# Optimized for high contrast on white or light-grey backgrounds.
LIGHT_THEME_STYLES = {
    # Dashboard components
    "dashboard.header": "bold blue",
    "dashboard.title": "bold dark_magenta",
    "dashboard.border": "blue",
    "dashboard.info": "bold dark_orange",
    "dashboard.project": "bold blue",
    "dashboard.session": "bold black",
    
    # Metrics and Data
    "metric.label": "black",
    "metric.value": "bold black",
    "metric.important": "bold blue",
    "metric.tokens": "bold blue",
    "metric.cost": "bold black",
    
    # Flash highlight for real-time value changes
    "metric.flash": "bold dark_orange",      # 通用数值变化 - 橙色醒目
    "metric.flash.cost": "bold dark_green",  # 成本变化
    "metric.flash.tokens": "bold dark_green", # Token 变化
    
    # Status and Indicators
    "status.success": "dark_green",
    "status.warning": "dark_orange",
    "status.error": "red",
    "status.info": "blue",
    "status.active": "dark_green",
    "status.idle": "grey37",
    
    # Tables
    "table.header": "bold blue",
    "table.title": "bold dark_magenta",
    "table.row.main": "black",
    "table.row.dim": "grey37",
    "table.row.project": "blue",
    "table.row.model": "dark_goldenrod",
    "table.row.time": "blue",
    "table.row.cost": "red",
    "table.row.tokens": "bold blue",
    "table.footer": "bold black",
}

def get_theme(theme_name: str = "dark") -> Theme:
    """Retrieve the Rich Theme object based on the theme name.

    Args:
        theme_name: The name of the theme ("light" or "dark").
                   Defaults to "dark".

    Returns:
        A rich.theme.Theme instance populated with semantic styles.
    """
    if theme_name.lower() == "light":
        return Theme(LIGHT_THEME_STYLES)
    
    # Default to Dark Theme
    return Theme(DARK_THEME_STYLES)

