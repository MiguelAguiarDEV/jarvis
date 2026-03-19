"""Async audio playback via PyAudio."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from numpy.typing import NDArray

log = structlog.get_logger()

# PyAudio requires portaudio system library. Optional import.
_pyaudio: Any = None
_PA_INT16: int = 8  # pyaudio.paInt16 constant fallback

try:
    import pyaudio as _pyaudio_mod

    _pyaudio = _pyaudio_mod
    _PA_INT16 = _pyaudio_mod.paInt16
except ImportError:
    pass


class AudioPlaybackError(Exception):
    """Raised when audio playback fails."""


def _require_pyaudio() -> Any:
    """Raise if pyaudio is not installed."""
    if _pyaudio is None:
        msg = (
            "pyaudio is not installed. "
            "Install with: uv sync --extra audio "
            "(requires portaudio system library)"
        )
        raise AudioPlaybackError(msg)
    return _pyaudio


class AudioPlayback:
    """Async wrapper around PyAudio speaker output stream.

    Plays float32 or int16 PCM audio at configurable sample rate.
    Does NOT generate audio — only plays provided buffers.
    """

    def __init__(self, sample_rate: int = 24_000, channels: int = 1) -> None:
        """Initialize audio playback.

        Args:
            sample_rate: Default sample rate for playback.
            channels: Number of audio channels (1=mono, 2=stereo).
        """
        self._sample_rate = sample_rate
        self._channels = channels
        self._pa: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    async def start(self) -> None:
        """Initialize PyAudio instance.

        Raises:
            AudioPlaybackError: If PyAudio fails to initialize.
        """
        pa = _require_pyaudio()
        self._loop = asyncio.get_running_loop()
        try:
            self._pa = pa.PyAudio()
            log.info("audio.playback.started", sample_rate=self._sample_rate)
        except OSError as e:
            msg = f"Failed to initialize audio playback: {e}"
            raise AudioPlaybackError(msg) from e

    async def play(self, audio: NDArray[np.float32], sample_rate: int | None = None) -> None:
        """Play audio buffer to speakers.

        Converts float32 [-1.0, 1.0] to int16 internally.
        Opens a stream per call (simple, avoids sample rate mismatch issues).

        Args:
            audio: Float32 numpy array, values in [-1.0, 1.0].
            sample_rate: Sample rate of the audio data. Uses default if None.

        Raises:
            AudioPlaybackError: If playback fails.
        """
        if self._pa is None or self._loop is None:
            msg = "Playback not started. Call start() first."
            raise AudioPlaybackError(msg)

        rate = sample_rate or self._sample_rate
        pcm = float_to_pcm_bytes(audio)

        try:
            stream = self._pa.open(
                format=_PA_INT16,
                channels=self._channels,
                rate=rate,
                output=True,
            )
            try:
                await self._loop.run_in_executor(None, stream.write, pcm)
            finally:
                stream.stop_stream()
                stream.close()
        except OSError as e:
            log.error("audio.playback.error", error=str(e))
            msg = f"Playback failed: {e}"
            raise AudioPlaybackError(msg) from e

    async def play_stream(
        self,
        chunks: AsyncIterator[tuple[NDArray[np.float32], int]],
    ) -> None:
        """Play streaming audio chunks as they arrive.

        Args:
            chunks: Async iterator yielding (audio_array, sample_rate) tuples.
        """
        async for audio, rate in chunks:
            await self.play(audio, rate)

    async def stop(self) -> None:
        """Terminate PyAudio instance."""
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None
        log.info("audio.playback.stopped")

    async def __aenter__(self) -> AudioPlayback:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()


def float_to_pcm_bytes(audio: NDArray[np.float32]) -> bytes:
    """Convert float32 [-1.0, 1.0] array to 16-bit PCM bytes."""
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    return pcm.tobytes()
