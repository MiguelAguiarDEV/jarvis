"""Tools screen — view registered tools and their schemas."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from jarvis.tools.base import ToolDefinition


class ToolsScreen(Screen[None]):
    """Displays registered tools with their schemas."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self, tool_definitions: list[ToolDefinition]) -> None:
        super().__init__()
        self._tools = tool_definitions

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static(f"[bold]Registered Tools ({len(self._tools)})[/bold]\n")

            if not self._tools:
                yield Static("[dim]No tools registered.[/dim]")
            else:
                for tool in self._tools:
                    schema = json.dumps(tool.parameters, indent=2)
                    yield Static(
                        f"[bold cyan]{tool.name}[/bold cyan]\n"
                        f"  {tool.description}\n"
                        f"  [dim]Parameters:[/dim]\n"
                        f"  [dim]{schema}[/dim]\n"
                    )
        yield Footer()

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
