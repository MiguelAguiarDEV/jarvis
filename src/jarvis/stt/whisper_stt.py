"""Speech-to-text using faster-whisper with on-demand VRAM management."""

from __future__ import annotations

import asyncio
import gc
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

log = structlog.get_logger()


class STTError(Exception):
    """Raised when STT operations fail."""


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """Result of a speech-to-text transcription."""

    text: str
    language: str
    language_probability: float
    duration_sec: float


class WhisperSTT:
    """On-demand GPU STT using faster-whisper.

    Loads model into VRAM only when transcription is needed.
    Unloads after transcription to free VRAM for other uses.
    Does NOT capture audio — receives numpy arrays.
    """

    def __init__(
        self,
        model_name: str = "large-v3-turbo",
        device: str = "cuda",
        compute_type: str = "float16",
    ) -> None:
        """Initialize STT engine.

        Args:
            model_name: Whisper model name or HuggingFace path.
            device: Device to run on ("cuda" or "cpu").
            compute_type: Quantization type ("float16", "int8_float16", "int8").
        """
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._model: Any = None
        self._lock = asyncio.Lock()

    @property
    def is_loaded(self) -> bool:
        """Whether the model is currently loaded in memory/VRAM."""
        return self._model is not None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def device(self) -> str:
        return self._device

    async def load_model(self) -> None:
        """Load model into VRAM. Runs in executor (blocking ~5-10s).

        Idempotent — no-op if already loaded.

        Raises:
            STTError: If model fails to load (CUDA OOM, missing model, etc.).
        """
        async with self._lock:
            if self._model is not None:
                return

            loop = asyncio.get_running_loop()
            try:
                self._model = await loop.run_in_executor(None, self._load_model_sync)
                log.info(
                    "stt.model_loaded",
                    model=self._model_name,
                    device=self._device,
                    compute_type=self._compute_type,
                )
            except Exception as e:
                self._model = None
                msg = f"Failed to load STT model '{self._model_name}': {e}"
                raise STTError(msg) from e

    def _load_model_sync(self) -> Any:
        """Synchronous model load."""
        from faster_whisper import WhisperModel

        return WhisperModel(
            self._model_name,
            device=self._device,
            compute_type=self._compute_type,
        )

    async def unload_model(self) -> None:
        """Delete model to release VRAM. Idempotent.

        Forces garbage collection and CUDA cache clear to ensure VRAM is freed.
        """
        async with self._lock:
            if self._model is None:
                return

            self._model = None
            gc.collect()

            # Clear CUDA cache if available
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

            log.info("stt.model_unloaded", model=self._model_name)

    async def transcribe(
        self,
        audio: NDArray[np.float32],
        language: str | None = "en",
    ) -> TranscriptionResult:
        """Transcribe audio array. Auto-loads model if not loaded.

        Args:
            audio: Float32 numpy array, 16kHz sample rate.
            language: Language code or None for auto-detect.

        Returns:
            TranscriptionResult with full text and metadata.

        Raises:
            STTError: On transcription failure.
        """
        if not self.is_loaded:
            await self.load_model()

        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                audio,
                language,
            )
            return result
        except STTError:
            raise
        except Exception as e:
            msg = f"Transcription failed: {e}"
            raise STTError(msg) from e

    def _transcribe_sync(
        self,
        audio: NDArray[np.float32],
        language: str | None,
    ) -> TranscriptionResult:
        """Synchronous transcription."""
        if self._model is None:
            msg = "Model not loaded"
            raise STTError(msg)

        segments, info = self._model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,
            without_timestamps=True,
        )

        # Consume the generator to get all text
        text = " ".join(segment.text.strip() for segment in segments)

        return TranscriptionResult(
            text=text.strip(),
            language=info.language,
            language_probability=info.language_probability,
            duration_sec=info.duration,
        )

    async def transcribe_and_unload(
        self,
        audio: NDArray[np.float32],
        language: str | None = "en",
    ) -> TranscriptionResult:
        """Convenience: transcribe then immediately unload VRAM.

        Args:
            audio: Float32 numpy array, 16kHz sample rate.
            language: Language code or None for auto-detect.

        Returns:
            TranscriptionResult with full text and metadata.
        """
        try:
            return await self.transcribe(audio, language)
        finally:
            await self.unload_model()
