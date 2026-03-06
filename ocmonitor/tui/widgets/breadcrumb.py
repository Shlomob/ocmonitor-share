"""Breadcrumb navigation bar widget."""

from typing import List

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class BreadcrumbBar(Static):
    """Displays a breadcrumb path like 'Home > Sessions > Detail'."""

    path: reactive[list] = reactive(list, always_update=True)

    def render(self) -> str:
        if not self.path:
            return "Home"
        return " > ".join(self.path)
