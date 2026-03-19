"""Voice Activity Detection using Silero VAD."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import structlog
import torch

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

log = structlog.get_logger()


class VADError(Exception):
    """Raised when VAD operations fail."""


@dataclass(frozen=True, slots=True)
class SpeechEvent:
    """Represents a speech start or end event from VAD."""

    type: Literal["start", "end"]
    timestamp_sec: float


class VoiceActivityDetector:
    """Wraps Silero VAD for streaming speech detection.

    Processes 512-sample chunks (32ms at 16kHz).
    Returns SpeechEvent on state transitions, None otherwise.
    Does NOT buffer audio — caller is responsible for accumulating speech frames.
    """

    CHUNK_SAMPLES: int = 512
    SAMPLE_RATE: int = 16_000

    def __init__(
        self,
        threshold: float = 0.5,
        min_silence_ms: int = 300,
        speech_pad_ms: int = 30,
    ) -> None:
        """Initialize VAD.

        Args:
            threshold: Speech probability threshold (0.0-1.0).
            min_silence_ms: Minimum silence duration to trigger speech end.
            speech_pad_ms: Padding added before/after speech segments.
        """
        self._threshold = threshold
        self._min_silence_ms = min_silence_ms
        self._speech_pad_ms = speech_pad_ms
        self._model: Any = None
        self._iterator: Any = None
        self._sample_count: int = 0

    @property
    def is_loaded(self) -> bool:
        """Whether the VAD model is loaded."""
        return self._model is not None and self._iterator is not None

    async def load(self) -> None:
        """Load Silero VAD model. Runs in executor (torch model load is blocking).

        Raises:
            VADError: If model fails to load.
        """
        if self.is_loaded:
            return

        loop = asyncio.get_running_loop()
        try:
            self._model = await loop.run_in_executor(None, self._load_model)
            self._iterator = self._create_iterator()
            self._sample_count = 0
            log.info(
                "vad.loaded",
                threshold=self._threshold,
                min_silence_ms=self._min_silence_ms,
            )
        except Exception as e:
            msg = f"Failed to load Silero VAD model: {e}"
            raise VADError(msg) from e

    def _load_model(self) -> Any:
        """Synchronous model load."""
        import silero_vad

        return silero_vad.load_silero_vad()

    def _create_iterator(self) -> Any:
        """Create a new VADIterator from the loaded model."""
        import silero_vad

        return silero_vad.VADIterator(
            self._model,
            threshold=self._threshold,
            sampling_rate=self.SAMPLE_RATE,
            min_silence_duration_ms=self._min_silence_ms,
            speech_pad_ms=self._speech_pad_ms,
        )

    def process_chunk(self, audio_chunk: NDArray[np.float32]) -> SpeechEvent | None:
        """Process a single 512-sample float32 audio chunk.

        Args:
            audio_chunk: Float32 numpy array, 512 samples, values in [-1.0, 1.0].

        Returns:
            SpeechEvent if speech started/ended, None otherwise.

        Raises:
            VADError: If model is not loaded.
        """
        if not self.is_loaded:
            msg = "VAD model not loaded. Call load() first."
            raise VADError(msg)

        tensor = torch.from_numpy(audio_chunk)
        result = self._iterator(tensor, return_seconds=True)
        self._sample_count += len(audio_chunk)

        if result is None:
            return None

        if "start" in result:
            return SpeechEvent(type="start", timestamp_sec=result["start"])
        if "end" in result:
            return SpeechEvent(type="end", timestamp_sec=result["end"])

        return None

    def reset(self) -> None:
        """Reset VAD state between utterances."""
        if self._iterator is not None:
            self._iterator.reset_states()
        self._sample_count = 0

    async def unload(self) -> None:
        """Unload model to free memory."""
        self._iterator = None
        self._model = None
        self._sample_count = 0
        log.info("vad.unloaded")
