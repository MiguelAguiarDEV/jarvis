"""Providers screen — configure LLM provider authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Select, Static

from jarvis.setup.env_writer import update_env

if TYPE_CHECKING:
    from textual.app import ComposeResult


class ProvidersScreen(Screen[None]):
    """Configure LLM provider credentials."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="wizard-content"):
            yield Static("[bold]LLM Provider Configuration[/bold]", classes="section-title")
            yield Static(
                "  Configure at least one provider. Claude or ChatGPT recommended.\n"
                "  Qwen (Ollama) works as offline fallback.\n"
            )

            # Claude
            yield Static("[bold cyan]Claude (Anthropic)[/bold cyan]", classes="section-title")
            yield Static("  Run `claude setup-token` in a terminal, then paste the token below.")
            yield Input(
                placeholder="Paste Claude setup-token here...", id="claude-token", password=True
            )
            yield Static("", id="claude-status")

            # ChatGPT
            yield Static("[bold green]ChatGPT (OpenAI)[/bold green]", classes="section-title")
            yield Static("  OAuth PKCE flow — click Authenticate to open browser.")
            yield Button("Authenticate with OpenAI", id="chatgpt-auth-btn")
            yield Static("", id="chatgpt-status")

            # Qwen/Ollama
            yield Static(
                "[bold yellow]Qwen (Ollama — Local)[/bold yellow]", classes="section-title"
            )
            yield Static("  Requires Ollama running locally. Install from ollama.com")
            yield Button("Detect Ollama", id="ollama-detect-btn")
            yield Static("", id="ollama-status")

            # Preferred
            yield Static("")
            yield Static("[bold]Preferred Provider[/bold]", classes="section-title")
            yield Select(
                [("claude", "claude"), ("chatgpt", "chatgpt"), ("qwen", "qwen")],
                value="claude",
                id="preferred-provider",
            )

            yield Static("")
            yield Button("Continue →", variant="primary", id="continue-btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-btn":
            self._save_and_continue()
        elif event.button.id == "chatgpt-auth-btn":
            self._start_chatgpt_auth()
        elif event.button.id == "ollama-detect-btn":
            self.run_worker(self._detect_ollama(), name="detect-ollama")

    def _save_and_continue(self) -> None:
        """Save provider config to .env and advance."""
        claude_token = self.query_one("#claude-token", Input).value.strip()
        preferred = self.query_one("#preferred-provider", Select)
        preferred_value = str(preferred.value) if preferred.value else "claude"

        if claude_token:
            update_env("JARVIS_CLAUDE_TOKEN", claude_token)

        update_env("JARVIS_LLM_PREFERRED", preferred_value)

        self.app.push_screen("verify")

    def _start_chatgpt_auth(self) -> None:
        """Start ChatGPT OAuth PKCE flow."""
        status = self.query_one("#chatgpt-status", Static)
        status.update(
            "[yellow]OAuth PKCE flow not yet implemented. Use API key in .env for now.[/yellow]"
        )

    async def _detect_ollama(self) -> None:
        from jarvis.setup.detectors import detect_ollama

        status = self.query_one("#ollama-status", Static)
        status.update("[dim]Checking...[/dim]")

        running, models = await detect_ollama()
        if running:
            model_list = ", ".join(models[:5]) if models else "no models"
            status.update(f"[green]✓ Ollama running — {model_list}[/green]")
            update_env("JARVIS_OLLAMA_BASE_URL", "http://localhost:11434")
            if any("qwen" in m for m in models):
                qwen_model = next(m for m in models if "qwen" in m)
                update_env("JARVIS_OLLAMA_MODEL", qwen_model)
        else:
            status.update(
                "[red]✗ Ollama not running[/red]\n"
                "  Install: https://ollama.com\n"
                "  Then: ollama pull qwen3.5:9b"
            )

    def action_go_back(self) -> None:
        self.app.pop_screen()
