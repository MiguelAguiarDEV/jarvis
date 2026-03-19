"""Complete screen — setup finished, launch options."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult


class CompleteScreen(Screen[None]):
    """Final screen: summary and launch options."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="wizard-content"):
            yield Static(
                "\n"
                "  [bold green]╔═══════════════════════════════════════╗[/bold green]\n"
                "  [bold green]║       Setup Complete!                 ║[/bold green]\n"
                "  [bold green]╚═══════════════════════════════════════╝[/bold green]\n"
                "\n"
                "  JARVIS is configured and ready to use.\n"
                "\n"
                "  [bold]How to run:[/bold]\n"
                "    • [cyan]python -m jarvis[/cyan]          Dashboard TUI\n"
                "    • [cyan]python -m jarvis --headless[/cyan] Voice-only mode\n"
                "    • [cyan]python -m jarvis setup[/cyan]     Re-run this wizard\n"
                "\n"
                "  [bold]Quick start:[/bold]\n"
                "    1. Run [cyan]python -m jarvis[/cyan]\n"
                '    2. Say "Hey Jarvis, what time is it?"\n'
                "    3. JARVIS will respond with the current time!\n",
            )
            yield Button("Launch JARVIS", variant="primary", id="launch-btn")
            yield Button("Exit", id="exit-btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "launch-btn":
            self.app.exit(message="launch")
        elif event.button.id == "exit-btn":
            self.app.exit()

    def action_quit(self) -> None:
        self.app.exit()
