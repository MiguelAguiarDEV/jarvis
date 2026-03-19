"""Welcome screen — system scan and overview."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from jarvis.setup.detectors import (
    DetectionResult,
    GPUInfo,
    run_all_detections,
)

if TYPE_CHECKING:
    from textual.app import ComposeResult


class WelcomeScreen(Screen[None]):
    """First screen: welcome banner + system scan."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="wizard-content"):
            yield Static(
                "\n"
                "  [bold cyan]╔═══════════════════════════════════════╗[/bold cyan]\n"
                "  [bold cyan]║         JARVIS Setup Wizard           ║[/bold cyan]\n"
                "  [bold cyan]╚═══════════════════════════════════════╝[/bold cyan]\n"
                "\n"
                "  Welcome! This wizard will configure your JARVIS installation.\n",
                classes="wizard-title",
            )
            yield Static("[bold]System Scan[/bold]", classes="section-title")
            yield Static("[dim]Scanning...[/dim]", id="scan-results")
            yield Static("")
            yield Button("Continue →", variant="primary", id="continue-btn", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._run_scan(), name="system-scan")

    async def _run_scan(self) -> None:
        results = await run_all_detections()
        self._render_results(results)
        btn = self.query_one("#continue-btn", Button)
        btn.disabled = False

    def _render_results(self, results: dict) -> None:
        lines: list[str] = []

        # Python
        py = results["python"]
        if isinstance(py, DetectionResult):
            icon = "[green]✓[/green]" if py.found else "[red]✗[/red]"
            lines.append(f"  {icon} {py.name}: {py.detail}")

        # uv
        uv = results["uv"]
        if isinstance(uv, DetectionResult):
            icon = "[green]✓[/green]" if uv.found else "[red]✗[/red]"
            lines.append(f"  {icon} {uv.name}: {uv.detail}")

        # CUDA/GPU
        gpu = results["cuda"]
        if isinstance(gpu, GPUInfo):
            if gpu.found:
                lines.append(f"  [green]✓[/green] GPU: {gpu.name} ({gpu.vram_mb}MB VRAM)")
            else:
                lines.append("  [yellow]○[/yellow] GPU: not detected (STT will use CPU)")

        # Audio devices
        devices = results["audio_devices"]
        if isinstance(devices, list):
            inputs = [d for d in devices if d.is_input]
            outputs = [d for d in devices if not d.is_input]
            lines.append(
                f"  {'[green]✓[/green]' if inputs else '[red]✗[/red]'} Microphones: {len(inputs)} found"
            )
            lines.append(
                f"  {'[green]✓[/green]' if outputs else '[red]✗[/red]'} Speakers: {len(outputs)} found"
            )
        else:
            lines.append("  [yellow]○[/yellow] Audio: PyAudio not installed")

        # Ollama
        ollama = results["ollama"]
        if isinstance(ollama, tuple):
            running, models = ollama
            if running:
                lines.append(f"  [green]✓[/green] Ollama: running ({len(models)} models)")
            else:
                lines.append("  [yellow]○[/yellow] Ollama: not running")

        # .env
        env = results["env_file"]
        if isinstance(env, DetectionResult):
            icon = "[green]✓[/green]" if env.found else "[dim]○[/dim]"
            lines.append(f"  {icon} Config: {env.detail}")

        # TTS models
        tts = results["tts_models"]
        if isinstance(tts, DetectionResult):
            icon = "[green]✓[/green]" if tts.found else "[yellow]○[/yellow]"
            lines.append(f"  {icon} TTS Models: {tts.detail}")

        scan_widget = self.query_one("#scan-results", Static)
        scan_widget.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-btn":
            self.app.push_screen("models")

    def action_quit(self) -> None:
        self.app.exit()
