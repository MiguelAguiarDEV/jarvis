"""Settings screen — edit JARVIS configuration interactively."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static

from jarvis.config import JarvisSettings
from jarvis.setup.env_writer import update_env

if TYPE_CHECKING:
    from textual.app import ComposeResult


class SettingsScreen(Screen[None]):
    """Interactive settings editor.

    Reads current JarvisSettings, renders as form fields,
    saves changes to .env on submit.
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        settings = JarvisSettings()

        yield Header()
        with VerticalScroll():
            yield Static("[bold]Settings[/bold]\n", id="settings-title")

            # LLM
            yield Label("LLM Preferred Provider")
            yield Select(
                [(p, p) for p in ("claude", "chatgpt", "qwen")],
                value=settings.llm_preferred,
                id="llm_preferred",
            )

            # STT
            yield Label("STT Model")
            yield Input(value=settings.stt_model, id="stt_model", placeholder="large-v3-turbo")
            yield Label("STT Device")
            yield Select(
                [("cuda", "cuda"), ("cpu", "cpu")],
                value=settings.stt_device,
                id="stt_device",
            )

            # TTS
            yield Label("TTS Voice")
            yield Input(value=settings.tts_voice, id="tts_voice", placeholder="af_sarah")
            yield Label("TTS Speed")
            yield Input(value=str(settings.tts_speed), id="tts_speed", placeholder="1.0")

            # Wake Word
            yield Label("Wake Word Threshold")
            yield Input(
                value=str(settings.wake_threshold),
                id="wake_threshold",
                placeholder="0.5",
            )

            # VAD
            yield Label("VAD Silence (ms)")
            yield Input(
                value=str(settings.vad_silence_ms),
                id="vad_silence_ms",
                placeholder="300",
            )

            # Log Level
            yield Label("Log Level")
            yield Select(
                [(lv, lv) for lv in ("DEBUG", "INFO", "WARNING", "ERROR")],
                value=settings.log_level,
                id="log_level",
            )

            yield Static("")  # spacer
            yield Button("Save", variant="primary", id="save-btn")
            yield Static("", id="save-status")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save_settings()

    def _save_settings(self) -> None:
        """Read form values and write to .env."""
        field_map = {
            "llm_preferred": "JARVIS_LLM_PREFERRED",
            "stt_model": "JARVIS_STT_MODEL",
            "stt_device": "JARVIS_STT_DEVICE",
            "tts_voice": "JARVIS_TTS_VOICE",
            "tts_speed": "JARVIS_TTS_SPEED",
            "wake_threshold": "JARVIS_WAKE_THRESHOLD",
            "vad_silence_ms": "JARVIS_VAD_SILENCE_MS",
            "log_level": "JARVIS_LOG_LEVEL",
        }

        try:
            for widget_id, env_key in field_map.items():
                widget = self.query_one(f"#{widget_id}")
                if isinstance(widget, Input):
                    value = widget.value
                elif isinstance(widget, Select):
                    value = str(widget.value) if widget.value is not None else ""
                else:
                    continue
                update_env(env_key, value)

            status = self.query_one("#save-status", Static)
            status.update(
                "[green]Settings saved to .env. Restart for changes to take effect.[/green]"
            )
        except Exception as e:
            status = self.query_one("#save-status", Static)
            status.update(f"[red]Error saving: {e}[/red]")

    def action_pop_screen(self) -> None:
        self.app.pop_screen()
