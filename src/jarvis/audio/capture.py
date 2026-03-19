"""Async microphone capture via PyAudio."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog

if TYPE_CHECKING:
    from numpy.typing import NDArray

log = structlog.get_logger()

# PyAudio requires portaudio system library. Optional import for environments
# where it's not available (CI, WSL without portaudio-dev).
_pyaudio: Any = None
_PA_INT16: int = 8  # pyaudio.paInt16 constant fallback

try:
    import pyaudio as _pyaudio_mod

    _pyaudio = _pyaudio_mod
    _PA_INT16 = _pyaudio_mod.paInt16
except ImportError:
    pass


class AudioCaptureError(Exception):
    """Raised when audio capture fails."""


def _require_pyaudio() -> Any:
    """Raise if pyaudio is not installed."""
    if _pyaudio is None:
        msg = (
            "pyaudio is not installed. "
            "Install with: uv sync --extra audio "
            "(requires portaudio system library)"
        )
        raise AudioCaptureError(msg)
    return _pyaudio


class AudioCapture:
    """Async wrapper around PyAudio microphone input stream.

    Captures 16-bit 16kHz mono PCM audio in configurable chunk sizes.
    Does NOT process audio — only captures and yields raw frames.
    """

    SAMPLE_RATE: int = 16_000
    CHANNELS: int = 1

    def __init__(self, chunk_ms: int = 32) -> None:
        """Initialize audio capture.

        Args:
            chunk_ms: Frame duration in milliseconds. 32ms = 512 samples at 16kHz.
        """
        if chunk_ms < 16 or chunk_ms % 16 != 0:
            msg = f"chunk_ms must be a positive multiple of 16, got {chunk_ms}"
            raise ValueError(msg)

        self._chunk_ms = chunk_ms
        self._chunk_samples = int(self.SAMPLE_RATE * chunk_ms / 1000)
        self._pa: Any = None
        self._stream: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def chunk_samples(self) -> int:
        """Number of samples per chunk."""
        return self._chunk_samples

    @property
    def chunk_bytes(self) -> int:
        """Number of bytes per chunk (16-bit = 2 bytes per sample)."""
        return self._chunk_samples * 2

    @property
    def is_active(self) -> bool:
        """Whether the stream is currently open and active."""
        return self._stream is not None and self._stream.is_active()

    async def start(self) -> None:
        """Open the PyAudio stream.

        Raises:
            AudioCaptureError: If no microphone is available or stream fails to open.
        """
        pa = _require_pyaudio()
        self._loop = asyncio.get_running_loop()
        try:
            self._pa = pa.PyAudio()
            self._stream = self._pa.open(
                format=_PA_INT16,
                channels=self.CHANNELS,
                rate=self.SAMPLE_RATE,
                input=True,
                frames_per_buffer=self._chunk_samples,
            )
            log.info(
                "audio.capture.started",
                sample_rate=self.SAMPLE_RATE,
                chunk_ms=self._chunk_ms,
                chunk_samples=self._chunk_samples,
            )
        except OSError as e:
            await self.stop()
            msg = f"Failed to open microphone: {e}"
            raise AudioCaptureError(msg) from e

    async def read_chunk(self) -> bytes:
        """Read one chunk of raw PCM bytes. Runs PyAudio read in executor.

        Returns:
            Raw PCM bytes of length chunk_bytes.

        Raises:
            AudioCaptureError: If stream is not active or read fails.
        """
        if not self.is_active or self._stream is None or self._loop is None:
            msg = "Audio stream is not active. Call start() first."
            raise AudioCaptureError(msg)

        try:
            data: bytes = await self._loop.run_in_executor(
                None,
                self._stream.read,
                self._chunk_samples,
                False,  # exception_on_overflow
            )
        except OSError as e:
            # Overflow — log and return silence
            log.warning("audio.capture.overflow", error=str(e))
            data = b"\x00" * self.chunk_bytes
        return data

    async def read_chunk_as_float(self) -> NDArray[np.float32]:
        """Read one chunk and convert to float32 array normalized to [-1.0, 1.0].

        Returns:
            Float32 numpy array of length chunk_samples.
        """
        raw = await self.read_chunk()
        return pcm_bytes_to_float(raw)

    async def stop(self) -> None:
        """Close the PyAudio stream and terminate PyAudio instance."""
        if self._stream is not None:
            try:
                if self._stream.is_active():
                    self._stream.stop_stream()
                self._stream.close()
            except OSError:
                pass
            self._stream = None

        if self._pa is not None:
            self._pa.terminate()
            self._pa = None

        log.info("audio.capture.stopped")

    async def __aenter__(self) -> AudioCapture:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()


def pcm_bytes_to_float(data: bytes) -> NDArray[np.float32]:
    """Convert 16-bit PCM bytes to float32 array normalized to [-1.0, 1.0]."""
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
