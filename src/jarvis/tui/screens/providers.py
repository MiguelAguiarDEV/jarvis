"""Providers screen — LLM provider health and configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Select, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from jarvis.llm.router import LLMRouter


class ProvidersScreen(Screen[None]):
    """Shows LLM provider status and allows switching preferred provider."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self, llm_router: LLMRouter, preferred: str) -> None:
        super().__init__()
        self._router = llm_router
        self._preferred = preferred
        self._health: dict[str, bool] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("[bold]LLM Providers[/bold]\n")
            yield Static("", id="provider-list")
            yield Static("")
            yield Static("[bold]Preferred Provider[/bold]")
            provider_names = list(self._router.providers.keys())
            yield Select(
                [(p, p) for p in provider_names],
                value=self._preferred,
                id="preferred-select",
            )
            yield Static("")
            yield Button("Health Check", variant="primary", id="health-btn")
            yield Static("", id="health-status")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._run_health_check(), name="health-check")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "health-btn":
            self.run_worker(self._run_health_check(), name="health-check")

    async def _run_health_check(self) -> None:
        status = self.query_one("#health-status", Static)
        status.update("[dim]Checking...[/dim]")

        self._health = await self._router.health_check()
        self._render_providers()

        status.update("[green]Health check complete.[/green]")

    def _render_providers(self) -> None:
        provider_list = self.query_one("#provider-list", Static)
        lines: list[str] = []

        for name, provider in self._router.providers.items():
            healthy = self._health.get(name)
            available = provider.is_available

            if healthy is True:
                icon = "[green]●[/green]"
                status = "healthy"
            elif healthy is False:
                icon = "[red]●[/red]"
                status = "offline"
            elif not available:
                icon = "[yellow]○[/yellow]"
                status = "not configured"
            else:
                icon = "[dim]○[/dim]"
                status = "unknown"

            preferred_tag = " [cyan](preferred)[/cyan]" if name == self._preferred else ""
            lines.append(f"  {icon} [bold]{name}[/bold] — {status}{preferred_tag}")

        provider_list.update("\n".join(lines) if lines else "[dim]No providers.[/dim]")

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
