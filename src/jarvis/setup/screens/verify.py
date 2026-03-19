"""Verify screen — run smoke tests to confirm setup works."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult


class VerifyScreen(Screen[None]):
    """Run verification checks on all configured components."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="wizard-content"):
            yield Static("[bold]Verification[/bold]", classes="section-title")
            yield Static("  Running component checks...\n")
            yield Static("", id="verify-results")
            yield Static("")
            yield Button("Finish Setup →", variant="primary", id="finish-btn", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._run_checks(), name="verify")

    async def _run_checks(self) -> None:
        results_widget = self.query_one("#verify-results", Static)
        lines: list[str] = []
        all_ok = True

        checks = [
            ("Config", self._check_config),
            ("Wake Word", self._check_wake_word),
            ("VAD", self._check_vad),
            ("TTS", self._check_tts),
            ("STT", self._check_stt_init),
        ]

        for name, check_fn in checks:
            lines.append(f"  [dim]○ {name}: checking...[/dim]")
            results_widget.update("\n".join(lines))

            try:
                ok, detail = await check_fn()
                icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
                lines[-1] = f"  {icon} {name}: {detail}"
                if not ok:
                    all_ok = False
            except Exception as e:
                lines[-1] = f"  [red]✗ {name}: {e}[/red]"
                all_ok = False

            results_widget.update("\n".join(lines))

        if all_ok:
            lines.append("\n  [bold green]All checks passed![/bold green]")
        else:
            lines.append(
                "\n  [bold yellow]Some checks failed. JARVIS may still work partially.[/bold yellow]"
            )

        results_widget.update("\n".join(lines))
        self.query_one("#finish-btn", Button).disabled = False

    async def _check_config(self) -> tuple[bool, str]:
        from jarvis.config import JarvisSettings

        settings = JarvisSettings()
        return True, f"loaded (preferred: {settings.llm_preferred})"

    async def _check_wake_word(self) -> tuple[bool, str]:
        from jarvis.audio.wake_word import WakeWordDetector

        ww = WakeWordDetector()
        await ww.load()
        available = (
            list(ww._model.models.keys()) if ww._model and hasattr(ww._model, "models") else []
        )
        await ww.unload()
        return "hey_jarvis" in available, f"{len(available)} models loaded"

    async def _check_vad(self) -> tuple[bool, str]:
        from jarvis.audio.vad import VoiceActivityDetector

        vad = VoiceActivityDetector()
        await vad.load()
        ok = vad.is_loaded
        await vad.unload()
        return ok, "Silero VAD loaded"

    async def _check_tts(self) -> tuple[bool, str]:
        from pathlib import Path

        model = Path("models/kokoro-v1.0.onnx")
        voices = Path("models/voices-v1.0.bin")

        if not model.exists() or not voices.exists():
            return False, "model files not found"

        from jarvis.tts.kokoro_tts import KokoroTTS

        tts = KokoroTTS()
        await tts.load()
        voice_count = len(tts.list_voices())
        await tts.unload()
        return True, f"{voice_count} voices available"

    async def _check_stt_init(self) -> tuple[bool, str]:
        from jarvis.stt.whisper_stt import WhisperSTT

        stt = WhisperSTT()
        return True, f"configured ({stt.model_name} on {stt.device})"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "finish-btn":
            self.app.push_screen("complete")

    def action_go_back(self) -> None:
        self.app.pop_screen()
