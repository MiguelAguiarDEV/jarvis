"""Text-to-speech using Kokoro-82M via ONNX Runtime (CPU only)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import numpy as np
    from numpy.typing import NDArray

log = structlog.get_logger()


class TTSError(Exception):
    """Raised when TTS operations fail."""


@dataclass(frozen=True, slots=True)
class TTSResult:
    """Result of text-to-speech synthesis."""

    audio: NDArray[np.float32]
    sample_rate: int


class KokoroTTS:
    """CPU-only TTS using kokoro-onnx.

    Loaded once at startup (CPU, ~300MB RAM, 0 VRAM).
    Does NOT play audio — returns numpy arrays.
    """

    DEFAULT_SAMPLE_RATE: int = 24_000

    def __init__(
        self,
        model_path: str = "models/kokoro-v1.0.onnx",
        voices_path: str = "models/voices-v1.0.bin",
        default_voice: str = "af_sarah",
        default_speed: float = 1.0,
    ) -> None:
        """Initialize TTS engine.

        Args:
            model_path: Path to kokoro ONNX model file.
            voices_path: Path to kokoro voices binary file.
            default_voice: Default voice name.
            default_speed: Default speech speed (0.5-2.0).
        """
        self._model_path = model_path
        self._voices_path = voices_path
        self._default_voice = default_voice
        self._default_speed = default_speed
        self._kokoro: Any = None

    @property
    def is_loaded(self) -> bool:
        """Whether the TTS model is loaded."""
        return self._kokoro is not None

    @property
    def default_voice(self) -> str:
        return self._default_voice

    @property
    def default_speed(self) -> float:
        return self._default_speed

    async def load(self) -> None:
        """Load ONNX model and voice data. Runs in executor.

        Raises:
            TTSError: If model files are not found or fail to load.
        """
        if self.is_loaded:
            return

        loop = asyncio.get_running_loop()
        try:
            self._kokoro = await loop.run_in_executor(None, self._load_sync)
            voices = self.list_voices()
            log.info(
                "tts.loaded",
                model=self._model_path,
                voices_count=len(voices),
                default_voice=self._default_voice,
            )
        except FileNotFoundError as e:
            msg = (
                f"TTS model files not found: {e}. "
                f"Download kokoro-v1.0.onnx and voices-v1.0.bin to the models/ directory."
            )
            raise TTSError(msg) from e
        except Exception as e:
            self._kokoro = None
            msg = f"Failed to load TTS model: {e}"
            raise TTSError(msg) from e

    def _load_sync(self) -> Any:
        """Synchronous model load."""
        from kokoro_onnx import Kokoro

        return Kokoro(self._model_path, self._voices_path)

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float | None = None,
        lang: str = "en-us",
    ) -> TTSResult:
        """Synthesize speech from text. Runs in executor.

        Args:
            text: Text to synthesize.
            voice: Voice name. Uses default if None.
            speed: Speed multiplier 0.5-2.0. Uses default if None.
            lang: Language code.

        Returns:
            TTSResult with float32 audio array and sample rate (24000).

        Raises:
            TTSError: If synthesis fails or model not loaded.
        """
        if not self.is_loaded:
            msg = "TTS model not loaded. Call load() first."
            raise TTSError(msg)

        if not text.strip():
            msg = "Cannot synthesize empty text."
            raise TTSError(msg)

        v = voice or self._default_voice
        s = speed or self._default_speed

        loop = asyncio.get_running_loop()
        try:
            audio, sample_rate = await loop.run_in_executor(
                None,
                self._synthesize_sync,
                text,
                v,
                s,
                lang,
            )
            log.debug(
                "tts.synthesized",
                text_length=len(text),
                audio_samples=len(audio),
                sample_rate=sample_rate,
                voice=v,
            )
            return TTSResult(audio=audio, sample_rate=sample_rate)
        except TTSError:
            raise
        except Exception as e:
            msg = f"TTS synthesis failed: {e}"
            raise TTSError(msg) from e

    def _synthesize_sync(
        self,
        text: str,
        voice: str,
        speed: float,
        lang: str,
    ) -> tuple[Any, int]:
        """Synchronous synthesis."""
        if self._kokoro is None:
            msg = "Model not loaded"
            raise TTSError(msg)

        result: tuple[Any, int] = self._kokoro.create(text, voice=voice, speed=speed, lang=lang)
        return result

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        speed: float | None = None,
        lang: str = "en-us",
    ) -> AsyncGenerator[TTSResult, None]:
        """Stream audio chunks as they are generated.

        Uses kokoro-onnx's create_stream() async generator.

        Args:
            text: Text to synthesize.
            voice: Voice name. Uses default if None.
            speed: Speed multiplier 0.5-2.0. Uses default if None.
            lang: Language code.

        Yields:
            TTSResult chunks with float32 audio and sample rate.

        Raises:
            TTSError: If synthesis fails or model not loaded.
        """
        if not self.is_loaded or self._kokoro is None:
            msg = "TTS model not loaded. Call load() first."
            raise TTSError(msg)

        if not text.strip():
            msg = "Cannot synthesize empty text."
            raise TTSError(msg)

        v = voice or self._default_voice
        s = speed or self._default_speed

        try:
            async for audio, sample_rate in self._kokoro.create_stream(
                text, voice=v, speed=s, lang=lang
            ):
                yield TTSResult(audio=audio, sample_rate=sample_rate)
        except Exception as e:
            msg = f"TTS streaming synthesis failed: {e}"
            raise TTSError(msg) from e

    def list_voices(self) -> list[str]:
        """List available voice names.

        Returns:
            List of voice name strings.

        Raises:
            TTSError: If model not loaded.
        """
        if not self.is_loaded or self._kokoro is None:
            msg = "TTS model not loaded. Call load() first."
            raise TTSError(msg)

        voices: list[str] = self._kokoro.get_voices()
        return voices

    async def unload(self) -> None:
        """Unload model to free memory."""
        self._kokoro = None
        log.info("tts.unloaded")
