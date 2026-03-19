"""JARVIS Setup Wizard — Textual application.

Guides first-time setup: system scan, model downloads,
LLM provider authentication, and verification.

Flow: Welcome → Models → Providers → Verify → Complete
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import App

from jarvis.setup.screens.complete import CompleteScreen
from jarvis.setup.screens.models import ModelsScreen
from jarvis.setup.screens.providers import ProvidersScreen
from jarvis.setup.screens.verify import VerifyScreen
from jarvis.setup.screens.welcome import WelcomeScreen


class SetupWizard(App[str | None]):
    """Setup wizard TUI application.

    Screens registered by name for push_screen("name") navigation.
    """

    TITLE = "JARVIS Setup"

    SCREENS: ClassVar[dict[str, type]] = {
        "welcome": WelcomeScreen,
        "models": ModelsScreen,
        "providers": ProvidersScreen,
        "verify": VerifyScreen,
        "complete": CompleteScreen,
    }

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen("welcome")

    def action_quit(self) -> None:
        self.exit()


def run_setup() -> None:
    """Entry point for setup wizard.

    If user clicks "Launch JARVIS" on complete screen,
    transitions to dashboard mode.
    """
    app = SetupWizard()
    result = app.run()

    if result == "launch":
        from jarvis.tui.app import run_dashboard

        run_dashboard()
