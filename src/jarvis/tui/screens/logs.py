"""Logs screen — live structured log viewer with filtering."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, RichLog, Select

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from jarvis.tui.log_buffer import LogEntry, TUILogBuffer


class LogsScreen(Screen[None]):
    """Live log viewer with level filtering and text search."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "pop_screen", "Back"),
        ("c", "clear_logs", "Clear"),
    ]

    def __init__(self, log_buffer: TUILogBuffer) -> None:
        super().__init__()
        self._log_buffer = log_buffer
        self._level_filter: str | None = None
        self._search_filter: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="log-filters"):
            yield Select(
                [
                    ("ALL", "ALL"),
                    ("DEBUG", "DEBUG"),
                    ("INFO", "INFO"),
                    ("WARNING", "WARNING"),
                    ("ERROR", "ERROR"),
                ],
                value="ALL",
                id="level-select",
            )
            yield Input(placeholder="Search logs...", id="log-search")
        yield RichLog(id="log-viewer", highlight=True, markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_logs()
        self.set_interval(1.0, self._refresh_logs)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "level-select":
            value = str(event.value) if event.value else "ALL"
            self._level_filter = None if value == "ALL" else value
            self._refresh_logs()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "log-search":
            self._search_filter = event.value if event.value.strip() else None
            self._refresh_logs()

    def _refresh_logs(self) -> None:
        viewer = self.query_one("#log-viewer", RichLog)
        viewer.clear()

        entries = self._log_buffer.get_filtered(
            level=self._level_filter,
            search=self._search_filter,
            limit=200,
        )

        for entry in reversed(entries):  # Show oldest first in viewer
            self._render_entry(viewer, entry)

    def _render_entry(self, viewer: RichLog, entry: LogEntry) -> None:
        level_color = {
            "debug": "dim",
            "info": "blue",
            "warning": "yellow",
            "error": "red",
            "critical": "red bold",
        }.get(entry.level.lower(), "white")

        fields_str = ""
        if entry.fields:
            fields_parts = [f"{k}={v}" for k, v in entry.fields.items()]
            fields_str = f" [{', '.join(fields_parts)}]"

        viewer.write(
            f"[dim]{entry.time_str}[/dim] "
            f"[{level_color}]{entry.level.upper():<8}[/{level_color}] "
            f"{entry.event}"
            f"[dim]{fields_str}[/dim]"
        )

    def action_clear_logs(self) -> None:
        self._log_buffer.clear()
        self._refresh_logs()

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
