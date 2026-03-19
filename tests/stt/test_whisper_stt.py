"""Tests for faster-whisper STT module."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from jarvis.stt.whisper_stt import STTError, TranscriptionResult, WhisperSTT


class TestTranscriptionResult:
    """Test TranscriptionResult dataclass."""

    def test_creation(self) -> None:
        result = TranscriptionResult(
            text="hello world",
            language="en",
            language_probability=0.98,
            duration_sec=2.5,
        )
        assert result.text == "hello world"
        assert result.language == "en"
        assert result.language_probability == 0.98
        assert result.duration_sec == 2.5

    def test_frozen(self) -> None:
        result = TranscriptionResult(
            text="test", language="en", language_probability=0.9, duration_sec=1.0
        )
        with pytest.raises(AttributeError):
            result.text = "changed"  # type: ignore[misc]


class TestWhisperSTT:
    """Test WhisperSTT engine."""

    def test_default_params(self) -> None:
        stt = WhisperSTT()
        assert stt.model_name == "large-v3-turbo"
        assert stt.device == "cuda"
        assert not stt.is_loaded

    def test_custom_params(self) -> None:
        stt = WhisperSTT(model_name="base", device="cpu", compute_type="int8")
        assert stt.model_name == "base"
        assert stt.device == "cpu"

    @pytest.mark.asyncio
    async def test_load_model(self) -> None:
        mock_model = MagicMock()

        with patch("jarvis.stt.whisper_stt.WhisperSTT._load_model_sync", return_value=mock_model):
            stt = WhisperSTT()
            await stt.load_model()

            assert stt.is_loaded

    @pytest.mark.asyncio
    async def test_load_model_is_idempotent(self) -> None:
        mock_model = MagicMock()

        with patch(
            "jarvis.stt.whisper_stt.WhisperSTT._load_model_sync", return_value=mock_model
        ) as load_mock:
            stt = WhisperSTT()
            await stt.load_model()
            await stt.load_model()

            load_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_model_failure_raises_stt_error(self) -> None:
        with patch(
            "jarvis.stt.whisper_stt.WhisperSTT._load_model_sync",
            side_effect=RuntimeError("CUDA OOM"),
        ):
            stt = WhisperSTT()
            with pytest.raises(STTError, match="Failed to load"):
                await stt.load_model()

            assert not stt.is_loaded

    @pytest.mark.asyncio
    async def test_unload_model(self) -> None:
        mock_model = MagicMock()

        with patch("jarvis.stt.whisper_stt.WhisperSTT._load_model_sync", return_value=mock_model):
            stt = WhisperSTT()
            await stt.load_model()
            assert stt.is_loaded

            await stt.unload_model()
            assert not stt.is_loaded

    @pytest.mark.asyncio
    async def test_unload_model_is_idempotent(self) -> None:
        stt = WhisperSTT()
        await stt.unload_model()
        await stt.unload_model()  # Should not raise

    @pytest.mark.asyncio
    async def test_transcribe_auto_loads(self) -> None:
        """Transcribe auto-loads model if not loaded."""

        @dataclass
        class MockInfo:
            language: str = "en"
            language_probability: float = 0.95
            duration: float = 2.0

        @dataclass
        class MockSegment:
            text: str = " hello world "

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([MockSegment()], MockInfo())

        with patch("jarvis.stt.whisper_stt.WhisperSTT._load_model_sync", return_value=mock_model):
            stt = WhisperSTT()
            audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
            result = await stt.transcribe(audio)

            assert result.text == "hello world"
            assert result.language == "en"
            assert result.language_probability == 0.95
            assert result.duration_sec == 2.0

    @pytest.mark.asyncio
    async def test_transcribe_joins_segments(self) -> None:
        """Multiple segments are joined with spaces."""

        @dataclass
        class MockInfo:
            language: str = "en"
            language_probability: float = 0.9
            duration: float = 5.0

        @dataclass
        class MockSegment:
            text: str = ""

        mock_model = MagicMock()
        segments = [MockSegment(text=" hello "), MockSegment(text=" world ")]
        mock_model.transcribe.return_value = (segments, MockInfo())

        with patch("jarvis.stt.whisper_stt.WhisperSTT._load_model_sync", return_value=mock_model):
            stt = WhisperSTT()
            audio = np.zeros(16000, dtype=np.float32)
            result = await stt.transcribe(audio)

            assert result.text == "hello world"

    @pytest.mark.asyncio
    async def test_transcribe_failure_raises_stt_error(self) -> None:
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("decode error")

        with patch("jarvis.stt.whisper_stt.WhisperSTT._load_model_sync", return_value=mock_model):
            stt = WhisperSTT()
            audio = np.zeros(16000, dtype=np.float32)
            with pytest.raises(STTError, match="Transcription failed"):
                await stt.transcribe(audio)

    @pytest.mark.asyncio
    async def test_transcribe_and_unload(self) -> None:
        """transcribe_and_unload loads, transcribes, then unloads."""

        @dataclass
        class MockInfo:
            language: str = "en"
            language_probability: float = 0.9
            duration: float = 1.0

        @dataclass
        class MockSegment:
            text: str = " test "

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([MockSegment()], MockInfo())

        with patch("jarvis.stt.whisper_stt.WhisperSTT._load_model_sync", return_value=mock_model):
            stt = WhisperSTT()
            audio = np.zeros(16000, dtype=np.float32)
            result = await stt.transcribe_and_unload(audio)

            assert result.text == "test"
            assert not stt.is_loaded  # Model should be unloaded

    @pytest.mark.asyncio
    async def test_transcribe_and_unload_unloads_on_error(self) -> None:
        """Model is unloaded even if transcription fails."""
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("fail")

        with patch("jarvis.stt.whisper_stt.WhisperSTT._load_model_sync", return_value=mock_model):
            stt = WhisperSTT()
            audio = np.zeros(16000, dtype=np.float32)

            with pytest.raises(STTError):
                await stt.transcribe_and_unload(audio)

            assert not stt.is_loaded  # Should still unload

    @pytest.mark.asyncio
    async def test_transcribe_passes_language(self) -> None:
        """Language parameter is passed to the model."""

        @dataclass
        class MockInfo:
            language: str = "es"
            language_probability: float = 0.85
            duration: float = 1.0

        @dataclass
        class MockSegment:
            text: str = " hola "

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([MockSegment()], MockInfo())

        with patch("jarvis.stt.whisper_stt.WhisperSTT._load_model_sync", return_value=mock_model):
            stt = WhisperSTT()
            audio = np.zeros(16000, dtype=np.float32)
            await stt.transcribe(audio, language="es")

            call_kwargs = mock_model.transcribe.call_args
            assert call_kwargs[1]["language"] == "es"

    @pytest.mark.asyncio
    async def test_transcribe_auto_detect_language(self) -> None:
        """None language triggers auto-detection."""

        @dataclass
        class MockInfo:
            language: str = "fr"
            language_probability: float = 0.7
            duration: float = 1.0

        @dataclass
        class MockSegment:
            text: str = " bonjour "

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([MockSegment()], MockInfo())

        with patch("jarvis.stt.whisper_stt.WhisperSTT._load_model_sync", return_value=mock_model):
            stt = WhisperSTT()
            audio = np.zeros(16000, dtype=np.float32)
            result = await stt.transcribe(audio, language=None)

            assert result.language == "fr"
            call_kwargs = mock_model.transcribe.call_args
            assert call_kwargs[1]["language"] is None
