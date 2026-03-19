"""Main dashboard screen — real-time pipeline status and activity."""

from __future__ import annotations

import time
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult  # noqa: TC002
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, RichLog, Static

from jarvis.tui.events import (  # noqa: TC001
    ConversationMessage,
    PipelineErrorMessage,
    PipelineReadyMessage,
    StateChangedMessage,
)


class StatusBar(Static):
    """Top bar showing pipeline state, wake word, and uptime."""

    state = reactive("idle")
    uptime_start: float = 0.0

    def on_mount(self) -> None:
        self.uptime_start = time.time()
        self.set_interval(1, self._update_uptime)

    def _update_uptime(self) -> None:
        self.update(self._render_status())

    def watch_state(self) -> None:
        self.update(self._render_status())

    def _render_status(self) -> str:
        elapsed = int(time.time() - self.uptime_start)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime = f"{hours}h {minutes:02d}m" if hours else f"{minutes}m {seconds:02d}s"

        state_icon = {
            "idle": "[dim]●[/dim]",
            "listening": "[green]●[/green]",
            "transcribing": "[yellow]●[/yellow]",
            "thinking": "[blue]●[/blue]",
            "speaking": "[cyan]●[/cyan]",
        }.get(self.state, "○")

        return (
            f" {state_icon} Status: [bold]{self.state.upper()}[/bold]"
            f"    Wake Word: hey jarvis"
            f"    Uptime: {uptime}"
        )


class ProviderPanel(Static):
    """Shows LLM provider health status."""

    def __init__(self) -> None:
        super().__init__()
        self._health: dict[str, bool] = {}

    def update_health(self, health: dict[str, bool]) -> None:
        self._health = health
        self._render()

    def _render(self) -> None:
        lines = ["[bold]Providers[/bold]"]
        for name, healthy in self._health.items():
            icon = "[green]●[/green]" if healthy else "[red]○[/red]"
            status = "healthy" if healthy else "offline"
            lines.append(f"  {icon} {name:<10} {status}")
        if not self._health:
            lines.append("  [dim]No providers configured[/dim]")
        self.update("\n".join(lines))


class HardwarePanel(Static):
    """Shows hardware status (mic, speaker, GPU, VRAM)."""

    def __init__(self) -> None:
        super().__init__()
        self._render_default()

    def _render_default(self) -> None:
        self.update(
            "[bold]Hardware[/bold]\n"
            "  Mic:     [dim]detecting...[/dim]\n"
            "  Speaker: [dim]detecting...[/dim]\n"
            "  GPU:     [dim]detecting...[/dim]\n"
            "  VRAM:    [dim]N/A[/dim]"
        )


class ActivityLog(RichLog):
    """Scrollable log of recent conversations."""

    def add_conversation(self, msg: ConversationMessage) -> None:
        ts = time.strftime("%H:%M:%S", time.localtime(msg.timestamp))
        tools = f" → {', '.join(msg.tool_names)}" if msg.tool_names else ""
        self.write(
            f"[dim]{ts}[/dim] "
            f'[bold]"{msg.user_text}"[/bold] '
            f"→ {msg.provider}{tools} "
            f"→ [green]{msg.elapsed_ms:.0f}ms[/green]"
        )

    def add_error(self, msg: PipelineErrorMessage) -> None:
        ts = time.strftime("%H:%M:%S", time.localtime(msg.timestamp))
        self.write(f"[dim]{ts}[/dim] [red]ERROR[/red] [{msg.stage}] {msg.error}")


class DashboardScreen(Screen[None]):
    """Main dashboard screen."""

    CSS_PATH = Path(__file__).parent.parent / "styles" / "dashboard.tcss"

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("s", "open_settings", "Settings"),
        ("l", "open_logs", "Logs"),
        ("t", "open_tools", "Tools"),
        ("p", "open_providers", "Providers"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield StatusBar(id="status-bar")
        with Horizontal(id="main-content"):
            with Container(id="left-panel"):
                yield ProviderPanel(id="provider-panel")
                yield HardwarePanel(id="hardware-panel")
            with Container(id="right-panel"):
                yield Label("[bold]Recent Activity[/bold]")
                yield ActivityLog(id="activity-log", highlight=True, markup=True)
        yield Footer()

    def on_state_changed_message(self, message: StateChangedMessage) -> None:
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.state = message.new_state

    def on_pipeline_ready_message(self, message: PipelineReadyMessage) -> None:
        provider_panel = self.query_one("#provider-panel", ProviderPanel)
        provider_panel.update_health(message.provider_health)

    def on_conversation_message(self, message: ConversationMessage) -> None:
        activity_log = self.query_one("#activity-log", ActivityLog)
        activity_log.add_conversation(message)

    def on_pipeline_error_message(self, message: PipelineErrorMessage) -> None:
        activity_log = self.query_one("#activity-log", ActivityLog)
        activity_log.add_error(message)

    def action_open_settings(self) -> None:
        from jarvis.tui.screens.settings import SettingsScreen

        self.app.push_screen(SettingsScreen())

    def action_open_logs(self) -> None:
        from jarvis.tui.screens.logs import LogsScreen

        app = self.app
        if hasattr(app, "_log_buffer"):
            self.app.push_screen(LogsScreen(app._log_buffer))

    def action_open_tools(self) -> None:
        from jarvis.tui.screens.tools import ToolsScreen

        app = self.app
        if hasattr(app, "_pipeline") and app._pipeline._tool_router:
            defs = app._pipeline._tool_router.get_definitions()
            self.app.push_screen(ToolsScreen(defs))

    def action_open_providers(self) -> None:
        from jarvis.tui.screens.providers import ProvidersScreen

        app = self.app
        if hasattr(app, "_pipeline") and app._pipeline._llm_router:
            self.app.push_screen(
                ProvidersScreen(app._pipeline._llm_router, app._settings.llm_preferred)
            )

    def action_quit(self) -> None:
        self.app.exit()
