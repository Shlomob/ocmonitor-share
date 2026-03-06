"""Filter bar widget for screen-level filtering."""

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Label, Select, Static


class FilterBar(Static):
    """Horizontal bar with filter controls."""

    class FilterChanged(Message):
        def __init__(self, filter_name: str, value: str) -> None:
            self.filter_name = filter_name
            self.value = value
            super().__init__()

    def __init__(
        self,
        filters: Optional[list] = None,
        **kwargs,
    ) -> None:
        """Initialize filter bar.

        Args:
            filters: List of dicts with keys: name, label, type ('select'|'input'),
                     and optionally 'options' for select type (list of (label, value) tuples).
        """
        super().__init__(**kwargs)
        self._filter_defs = filters or []

    def compose(self) -> ComposeResult:
        with Horizontal(classes="filter-bar-row"):
            for fdef in self._filter_defs:
                yield Label(fdef["label"], classes="filter-label")
                if fdef.get("type") == "select":
                    options = fdef.get("options", [])
                    yield Select(
                        options,
                        value=options[0][1] if options else Select.BLANK,
                        id=f"filter-{fdef['name']}",
                        classes="filter-select",
                    )
                else:
                    yield Input(
                        placeholder=fdef.get("placeholder", ""),
                        id=f"filter-{fdef['name']}",
                        classes="filter-input",
                    )

    def on_select_changed(self, event: Select.Changed) -> None:
        control_id = event.select.id or ""
        if control_id.startswith("filter-"):
            name = control_id[len("filter-"):]
            self.post_message(self.FilterChanged(name, str(event.value)))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        control_id = event.input.id or ""
        if control_id.startswith("filter-"):
            name = control_id[len("filter-"):]
            self.post_message(self.FilterChanged(name, event.value))
