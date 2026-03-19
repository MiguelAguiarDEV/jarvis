"""Tests for Wake Word Detection module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from jarvis.audio.wake_word import WakeWordDetector, WakeWordError


class TestWakeWordDetector:
    """Test WakeWordDetector."""

    def test_not_loaded_initially(self) -> None:
        ww = WakeWordDetector()
        assert not ww.is_loaded

    def test_default_params(self) -> None:
        ww = WakeWordDetector()
        assert ww.wake_word == "hey_jarvis"
        assert ww.threshold == 0.5

    def test_custom_params(self) -> None:
        ww = WakeWordDetector(wake_word="alexa", threshold=0.7)
        assert ww.wake_word == "alexa"
        assert ww.threshold == 0.7

    def test_process_frame_without_load_raises(self) -> None:
        ww = WakeWordDetector()
        with pytest.raises(WakeWordError, match="not loaded"):
            ww.process_frame(b"\x00" * 2560)

    @pytest.mark.asyncio
    async def test_load_creates_model(self) -> None:
        mock_model = MagicMock()
        mock_model.models = {"hey_jarvis": MagicMock()}

        with patch("jarvis.audio.wake_word.WakeWordDetector._load_model", return_value=mock_model):
            ww = WakeWordDetector()
            await ww.load()
            assert ww.is_loaded

    @pytest.mark.asyncio
    async def test_load_is_idempotent(self) -> None:
        mock_model = MagicMock()
        mock_model.models = {"hey_jarvis": MagicMock()}

        with patch(
            "jarvis.audio.wake_word.WakeWordDetector._load_model", return_value=mock_model
        ) as load_mock:
            ww = WakeWordDetector()
            await ww.load()
            await ww.load()
            load_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_frame_accumulates_small_chunks(self) -> None:
        """Small chunks are accumulated until 1280 samples (2560 bytes)."""
        mock_model = MagicMock()
        mock_model.models = {"hey_jarvis": MagicMock()}
        mock_model.predict.return_value = {"hey_jarvis": 0.0}

        with patch("jarvis.audio.wake_word.WakeWordDetector._load_model", return_value=mock_model):
            ww = WakeWordDetector()
            await ww.load()

            # 512 samples = 1024 bytes, not enough for 2560
            small_chunk = b"\x00" * 1024
            result = ww.process_frame(small_chunk)
            assert result == {}  # Not enough data
            mock_model.predict.assert_not_called()

            # Another 512 samples = 2048 total, still not enough
            result = ww.process_frame(small_chunk)
            assert result == {}
            mock_model.predict.assert_not_called()

            # Another 512 samples = 3072 total, enough for one frame (2560)
            result = ww.process_frame(small_chunk)
            assert result == {"hey_jarvis": 0.0}
            mock_model.predict.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_frame_full_frame(self) -> None:
        """Full 1280-sample frame triggers immediate prediction."""
        mock_model = MagicMock()
        mock_model.models = {"hey_jarvis": MagicMock()}
        mock_model.predict.return_value = {"hey_jarvis": 0.8}

        with patch("jarvis.audio.wake_word.WakeWordDetector._load_model", return_value=mock_model):
            ww = WakeWordDetector()
            await ww.load()

            full_frame = b"\x00" * 2560  # 1280 samples * 2 bytes
            result = ww.process_frame(full_frame)
            assert result == {"hey_jarvis": 0.8}

    @pytest.mark.asyncio
    async def test_process_frame_float(self) -> None:
        """Float32 input is converted to int16 PCM."""
        mock_model = MagicMock()
        mock_model.models = {"hey_jarvis": MagicMock()}
        mock_model.predict.return_value = {"hey_jarvis": 0.3}

        with patch("jarvis.audio.wake_word.WakeWordDetector._load_model", return_value=mock_model):
            ww = WakeWordDetector()
            await ww.load()

            # 1280 float32 samples
            audio = np.zeros(1280, dtype=np.float32)
            result = ww.process_frame_float(audio)
            assert result == {"hey_jarvis": 0.3}

    def test_detected_above_threshold(self) -> None:
        ww = WakeWordDetector(threshold=0.5)
        assert ww.detected({"hey_jarvis": 0.8})

    def test_detected_below_threshold(self) -> None:
        ww = WakeWordDetector(threshold=0.5)
        assert not ww.detected({"hey_jarvis": 0.3})

    def test_detected_at_threshold(self) -> None:
        ww = WakeWordDetector(threshold=0.5)
        assert ww.detected({"hey_jarvis": 0.5})

    def test_detected_empty_scores(self) -> None:
        ww = WakeWordDetector(threshold=0.5)
        assert not ww.detected({})

    def test_detected_missing_wake_word(self) -> None:
        ww = WakeWordDetector(wake_word="hey_jarvis", threshold=0.5)
        assert not ww.detected({"alexa": 0.9})

    @pytest.mark.asyncio
    async def test_reset_clears_accumulator(self) -> None:
        mock_model = MagicMock()
        mock_model.models = {"hey_jarvis": MagicMock()}

        with patch("jarvis.audio.wake_word.WakeWordDetector._load_model", return_value=mock_model):
            ww = WakeWordDetector()
            await ww.load()

            # Add some data to accumulator
            ww.process_frame(b"\x00" * 1024)
            assert len(ww._accumulator) > 0

            ww.reset()
            assert len(ww._accumulator) == 0
            mock_model.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_unload_clears_model(self) -> None:
        mock_model = MagicMock()
        mock_model.models = {"hey_jarvis": MagicMock()}

        with patch("jarvis.audio.wake_word.WakeWordDetector._load_model", return_value=mock_model):
            ww = WakeWordDetector()
            await ww.load()
            assert ww.is_loaded

            await ww.unload()
            assert not ww.is_loaded

    @pytest.mark.asyncio
    async def test_load_failure_raises_error(self) -> None:
        with patch(
            "jarvis.audio.wake_word.WakeWordDetector._load_model",
            side_effect=RuntimeError("download failed"),
        ):
            ww = WakeWordDetector()
            with pytest.raises(WakeWordError, match="Failed to load"):
                await ww.load()

    def test_reset_without_load_is_safe(self) -> None:
        ww = WakeWordDetector()
        ww.reset()  # Should not raise
