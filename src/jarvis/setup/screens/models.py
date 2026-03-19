"""Models screen — download TTS model files with progress."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, ProgressBar, Static

from jarvis.setup.detectors import detect_tts_models
from jarvis.setup.installers import download_tts_models

if TYPE_CHECKING:
    from textual.app import ComposeResult


class ModelsScreen(Screen[None]):
    """Download required model files."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="wizard-content"):
            yield Static("[bold]Model Downloads[/bold]", classes="section-title")
            yield Static("", id="model-status")
            yield Static("", id="download-file")
            yield ProgressBar(total=100, show_eta=True, id="progress-bar")
            yield Static("")
            yield Button("Download Models", variant="primary", id="download-btn")
            yield Button("Skip (already downloaded) →", id="skip-btn")
            yield Static("", id="download-result")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._check_existing(), name="check-models")

    async def _check_existing(self) -> None:
        result = await detect_tts_models()
        status = self.query_one("#model-status", Static)
        if result.found:
            status.update(f"[green]✓ TTS models already downloaded ({result.detail})[/green]")
            self.query_one("#download-btn", Button).disabled = True
        else:
            status.update(
                f"[yellow]○ {result.detail}[/yellow]\n\n"
                "  Required files:\n"
                "  • kokoro-v1.0.onnx (~330MB)\n"
                "  • voices-v1.0.bin (~8MB)\n"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "download-btn":
            event.button.disabled = True
            self.run_worker(self._download(), name="download-models")
        elif event.button.id == "skip-btn":
            self.app.push_screen("providers")

    async def _download(self) -> None:
        progress = self.query_one("#progress-bar", ProgressBar)
        file_label = self.query_one("#download-file", Static)
        result_label = self.query_one("#download-result", Static)

        try:
            async for update in download_tts_models():
                file_label.update(
                    f"  Downloading: {update.filename} "
                    f"({update.downloaded_mb:.1f}/{update.total_mb:.1f} MB)"
                )
                progress.update(progress=update.percent)

            result_label.update("[green]✓ All models downloaded successfully![/green]")
            # Auto-advance after short delay
            await self._advance_after_delay()
        except Exception as e:
            result_label.update(f"[red]✗ Download failed: {e}[/red]")
            self.query_one("#download-btn", Button).disabled = False

    async def _advance_after_delay(self) -> None:
        import asyncio

        await asyncio.sleep(1.5)
        self.app.push_screen("providers")

    def action_go_back(self) -> None:
        self.app.pop_screen()
