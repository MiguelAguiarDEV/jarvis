"""JARVIS Setup Wizard — Textual application.

Guides first-time setup: hardware detection, model downloads,
LLM provider authentication, and verification.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static


class SetupWizard(App[None]):
    """Setup wizard TUI application.

    Screens: Welcome → Hardware → Models → Providers → Verify → Complete
    """

    TITLE = "JARVIS Setup"

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "\n"
            "  [bold cyan]Welcome to JARVIS Setup[/bold cyan]\n"
            "\n"
            "  This wizard will configure your JARVIS installation.\n"
            "\n"
            "  [dim]Setup wizard screens coming in TUI Phase 3.[/dim]\n"
            "  [dim]Press Q to exit.[/dim]\n",
            id="welcome",
        )
        yield Footer()

    def action_quit(self) -> None:
        self.exit()


def run_setup() -> None:
    """Entry point for setup wizard."""
    app = SetupWizard()
    app.run()
