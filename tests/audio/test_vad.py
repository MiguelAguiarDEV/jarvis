"""Tests for Voice Activity Detection module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from jarvis.audio.vad import SpeechEvent, VADError, VoiceActivityDetector


class TestSpeechEvent:
    """Test SpeechEvent dataclass."""

    def test_start_event(self) -> None:
        event = SpeechEvent(type="start", timestamp_sec=1.5)
        assert event.type == "start"
        assert event.timestamp_sec == 1.5

    def test_end_event(self) -> None:
        event = SpeechEvent(type="end", timestamp_sec=3.2)
        assert event.type == "end"
        assert event.timestamp_sec == 3.2

    def test_frozen(self) -> None:
        """SpeechEvent is immutable."""
        event = SpeechEvent(type="start", timestamp_sec=1.0)
        with pytest.raises(AttributeError):
            event.type = "end"  # type: ignore[misc]


class TestVoiceActivityDetector:
    """Test VoiceActivityDetector."""

    def test_not_loaded_initially(self) -> None:
        vad = VoiceActivityDetector()
        assert not vad.is_loaded

    def test_default_params(self) -> None:
        vad = VoiceActivityDetector()
        assert vad._threshold == 0.5
        assert vad._min_silence_ms == 300
        assert vad._speech_pad_ms == 30

    def test_custom_params(self) -> None:
        vad = VoiceActivityDetector(threshold=0.7, min_silence_ms=500, speech_pad_ms=50)
        assert vad._threshold == 0.7
        assert vad._min_silence_ms == 500
        assert vad._speech_pad_ms == 50

    def test_process_chunk_without_load_raises(self) -> None:
        vad = VoiceActivityDetector()
        chunk = np.zeros(512, dtype=np.float32)
        with pytest.raises(VADError, match="not loaded"):
            vad.process_chunk(chunk)

    @pytest.mark.asyncio
    async def test_load_sets_model_and_iterator(self) -> None:
        mock_model = MagicMock()
        mock_iterator = MagicMock()

        with (
            patch("jarvis.audio.vad.VoiceActivityDetector._load_model", return_value=mock_model),
            patch(
                "jarvis.audio.vad.VoiceActivityDetector._create_iterator",
                return_value=mock_iterator,
            ),
        ):
            vad = VoiceActivityDetector()
            await vad.load()

            assert vad.is_loaded
            assert vad._model is mock_model
            assert vad._iterator is mock_iterator

    @pytest.mark.asyncio
    async def test_load_is_idempotent(self) -> None:
        mock_model = MagicMock()
        mock_iterator = MagicMock()

        with (
            patch(
                "jarvis.audio.vad.VoiceActivityDetector._load_model", return_value=mock_model
            ) as load_mock,
            patch(
                "jarvis.audio.vad.VoiceActivityDetector._create_iterator",
                return_value=mock_iterator,
            ),
        ):
            vad = VoiceActivityDetector()
            await vad.load()
            await vad.load()  # Second call should be no-op

            load_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_chunk_returns_none_for_silence(self) -> None:
        mock_model = MagicMock()
        mock_iterator = MagicMock()
        mock_iterator.return_value = None  # No speech event

        with (
            patch("jarvis.audio.vad.VoiceActivityDetector._load_model", return_value=mock_model),
            patch(
                "jarvis.audio.vad.VoiceActivityDetector._create_iterator",
                return_value=mock_iterator,
            ),
        ):
            vad = VoiceActivityDetector()
            await vad.load()

            chunk = np.zeros(512, dtype=np.float32)
            result = vad.process_chunk(chunk)
            assert result is None

    @pytest.mark.asyncio
    async def test_process_chunk_returns_start_event(self) -> None:
        mock_model = MagicMock()
        mock_iterator = MagicMock()
        mock_iterator.return_value = {"start": 0.5}

        with (
            patch("jarvis.audio.vad.VoiceActivityDetector._load_model", return_value=mock_model),
            patch(
                "jarvis.audio.vad.VoiceActivityDetector._create_iterator",
                return_value=mock_iterator,
            ),
        ):
            vad = VoiceActivityDetector()
            await vad.load()

            chunk = np.zeros(512, dtype=np.float32)
            result = vad.process_chunk(chunk)

            assert result is not None
            assert result.type == "start"
            assert result.timestamp_sec == 0.5

    @pytest.mark.asyncio
    async def test_process_chunk_returns_end_event(self) -> None:
        mock_model = MagicMock()
        mock_iterator = MagicMock()
        mock_iterator.return_value = {"end": 2.0}

        with (
            patch("jarvis.audio.vad.VoiceActivityDetector._load_model", return_value=mock_model),
            patch(
                "jarvis.audio.vad.VoiceActivityDetector._create_iterator",
                return_value=mock_iterator,
            ),
        ):
            vad = VoiceActivityDetector()
            await vad.load()

            chunk = np.zeros(512, dtype=np.float32)
            result = vad.process_chunk(chunk)

            assert result is not None
            assert result.type == "end"
            assert result.timestamp_sec == 2.0

    @pytest.mark.asyncio
    async def test_reset_clears_state(self) -> None:
        mock_model = MagicMock()
        mock_iterator = MagicMock()

        with (
            patch("jarvis.audio.vad.VoiceActivityDetector._load_model", return_value=mock_model),
            patch(
                "jarvis.audio.vad.VoiceActivityDetector._create_iterator",
                return_value=mock_iterator,
            ),
        ):
            vad = VoiceActivityDetector()
            await vad.load()

            # Process some chunks to increment sample count
            mock_iterator.return_value = None
            chunk = np.zeros(512, dtype=np.float32)
            vad.process_chunk(chunk)
            assert vad._sample_count == 512

            vad.reset()
            assert vad._sample_count == 0
            mock_iterator.reset_states.assert_called_once()

    @pytest.mark.asyncio
    async def test_unload_clears_model(self) -> None:
        mock_model = MagicMock()
        mock_iterator = MagicMock()

        with (
            patch("jarvis.audio.vad.VoiceActivityDetector._load_model", return_value=mock_model),
            patch(
                "jarvis.audio.vad.VoiceActivityDetector._create_iterator",
                return_value=mock_iterator,
            ),
        ):
            vad = VoiceActivityDetector()
            await vad.load()
            assert vad.is_loaded

            await vad.unload()
            assert not vad.is_loaded

    def test_reset_without_load_is_safe(self) -> None:
        """Reset on unloaded VAD should not raise."""
        vad = VoiceActivityDetector()
        vad.reset()  # Should not raise

    @pytest.mark.asyncio
    async def test_load_failure_raises_vad_error(self) -> None:
        with patch(
            "jarvis.audio.vad.VoiceActivityDetector._load_model",
            side_effect=RuntimeError("model not found"),
        ):
            vad = VoiceActivityDetector()
            with pytest.raises(VADError, match="Failed to load"):
                await vad.load()

    @pytest.mark.asyncio
    async def test_sample_count_increments(self) -> None:
        mock_model = MagicMock()
        mock_iterator = MagicMock()
        mock_iterator.return_value = None

        with (
            patch("jarvis.audio.vad.VoiceActivityDetector._load_model", return_value=mock_model),
            patch(
                "jarvis.audio.vad.VoiceActivityDetector._create_iterator",
                return_value=mock_iterator,
            ),
        ):
            vad = VoiceActivityDetector()
            await vad.load()

            chunk = np.zeros(512, dtype=np.float32)
            vad.process_chunk(chunk)
            vad.process_chunk(chunk)
            assert vad._sample_count == 1024
