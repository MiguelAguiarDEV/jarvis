"""Wake word detection using openWakeWord."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog

if TYPE_CHECKING:
    from numpy.typing import NDArray

log = structlog.get_logger()


class WakeWordError(Exception):
    """Raised when wake word operations fail."""


class WakeWordDetector:
    """Wraps openWakeWord for 'hey jarvis' detection.

    Processes 16-bit 16kHz PCM frames. openWakeWord expects int16 numpy arrays
    and works best with 1280-sample frames (80ms at 16kHz).

    Does NOT capture audio — receives frames from AudioCapture.
    """

    FRAME_SAMPLES: int = 1280  # 80ms at 16kHz, recommended by openWakeWord
    DEFAULT_THRESHOLD: float = 0.5

    def __init__(
        self,
        wake_word: str = "hey_jarvis",
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        """Initialize wake word detector.

        Args:
            wake_word: Wake word model key (e.g., "hey_jarvis").
            threshold: Detection confidence threshold (0.0-1.0).
        """
        self._wake_word = wake_word
        self._threshold = threshold
        self._model: Any = None
        self._accumulator: bytearray = bytearray()

    @property
    def is_loaded(self) -> bool:
        """Whether the wake word model is loaded."""
        return self._model is not None

    @property
    def wake_word(self) -> str:
        """The wake word key being detected."""
        return self._wake_word

    @property
    def threshold(self) -> float:
        """Detection confidence threshold."""
        return self._threshold

    async def load(self) -> None:
        """Load wake word model. Runs in executor (model download/load is blocking).

        Raises:
            WakeWordError: If model fails to load.
        """
        if self.is_loaded:
            return

        loop = asyncio.get_running_loop()
        try:
            self._model = await loop.run_in_executor(None, self._load_model)
            available = list(self._model.models.keys()) if hasattr(self._model, "models") else []
            log.info(
                "wake_word.loaded",
                wake_word=self._wake_word,
                threshold=self._threshold,
                available_models=available,
            )
            if self._wake_word not in available:
                log.warning(
                    "wake_word.model_not_found",
                    requested=self._wake_word,
                    available=available,
                )
        except Exception as e:
            msg = f"Failed to load wake word model: {e}"
            raise WakeWordError(msg) from e

    def _load_model(self) -> Any:
        """Synchronous model load."""
        from openwakeword.model import Model

        return Model(wakeword_model_paths=[], vad_threshold=0)

    def process_frame(self, pcm_bytes: bytes) -> dict[str, float]:
        """Process raw PCM bytes, accumulating until we have enough for a prediction.

        openWakeWord expects 1280-sample (80ms) int16 frames. This method
        accumulates smaller chunks and runs prediction when enough data is available.

        Args:
            pcm_bytes: Raw 16-bit PCM bytes, 16kHz mono.

        Returns:
            Dict mapping model name to confidence score (0.0 to 1.0).
            Returns empty dict if not enough data accumulated yet.

        Raises:
            WakeWordError: If model is not loaded.
        """
        if not self.is_loaded:
            msg = "Wake word model not loaded. Call load() first."
            raise WakeWordError(msg)

        self._accumulator.extend(pcm_bytes)

        # Need 1280 samples * 2 bytes = 2560 bytes for one frame
        frame_bytes = self.FRAME_SAMPLES * 2
        if len(self._accumulator) < frame_bytes:
            return {}

        # Extract one frame worth of data
        frame_data = bytes(self._accumulator[:frame_bytes])
        self._accumulator = self._accumulator[frame_bytes:]

        frame_int16 = np.frombuffer(frame_data, dtype=np.int16)
        result: dict[str, float] = self._model.predict(frame_int16)
        return result

    def process_frame_float(self, audio: NDArray[np.float32]) -> dict[str, float]:
        """Process float32 audio array by converting to int16 PCM bytes first.

        Args:
            audio: Float32 numpy array, values in [-1.0, 1.0].

        Returns:
            Dict mapping model name to confidence score.
        """
        pcm_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        return self.process_frame(pcm_int16.tobytes())

    def detected(self, scores: dict[str, float]) -> bool:
        """Check if the target wake word score exceeds threshold.

        Args:
            scores: Dict from process_frame().

        Returns:
            True if wake word detected above threshold.
        """
        if not scores:
            return False
        return scores.get(self._wake_word, 0.0) >= self._threshold

    def reset(self) -> None:
        """Reset model state and accumulator after activation."""
        if self._model is not None:
            self._model.reset()
        self._accumulator.clear()

    async def unload(self) -> None:
        """Unload model to free memory."""
        self._model = None
        self._accumulator.clear()
        log.info("wake_word.unloaded")
