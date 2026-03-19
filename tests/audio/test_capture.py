"""Tests for audio capture module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from jarvis.audio.capture import AudioCapture, AudioCaptureError, pcm_bytes_to_float


class TestPcmBytesToFloat:
    """Test PCM byte conversion utility."""

    def test_silence_converts_to_zeros(self) -> None:
        """Silent PCM bytes convert to all zeros."""
        silence = b"\x00" * 1024  # 512 samples
        result = pcm_bytes_to_float(silence)
        assert result.dtype == np.float32
        assert len(result) == 512
        np.testing.assert_array_equal(result, np.zeros(512, dtype=np.float32))

    def test_max_positive_converts_to_near_one(self) -> None:
        """Max positive int16 (32767) converts to ~1.0."""
        max_pcm = np.array([32767], dtype=np.int16).tobytes()
        result = pcm_bytes_to_float(max_pcm)
        assert abs(result[0] - 1.0) < 0.001

    def test_max_negative_converts_to_near_minus_one(self) -> None:
        """Max negative int16 (-32768) converts to -1.0."""
        min_pcm = np.array([-32768], dtype=np.int16).tobytes()
        result = pcm_bytes_to_float(min_pcm)
        assert abs(result[0] - (-1.0)) < 0.001

    def test_roundtrip_preserves_shape(self, tone_16k_mono: bytes) -> None:
        """Converting PCM bytes preserves sample count."""
        result = pcm_bytes_to_float(tone_16k_mono)
        assert len(result) == 512


class TestAudioCapture:
    """Test AudioCapture initialization and validation."""

    def test_valid_chunk_ms(self) -> None:
        """Valid chunk_ms values are accepted."""
        cap = AudioCapture(chunk_ms=32)
        assert cap.chunk_samples == 512
        assert cap.chunk_bytes == 1024

    def test_chunk_ms_80(self) -> None:
        """80ms chunk = 1280 samples."""
        cap = AudioCapture(chunk_ms=80)
        assert cap.chunk_samples == 1280

    def test_invalid_chunk_ms_not_multiple(self) -> None:
        """chunk_ms must be multiple of 16."""
        with pytest.raises(ValueError, match="multiple of 16"):
            AudioCapture(chunk_ms=30)

    def test_invalid_chunk_ms_too_small(self) -> None:
        """chunk_ms must be >= 16."""
        with pytest.raises(ValueError, match="multiple of 16"):
            AudioCapture(chunk_ms=8)

    def test_not_active_before_start(self) -> None:
        """Stream is not active before start()."""
        cap = AudioCapture()
        assert not cap.is_active

    @pytest.mark.asyncio
    async def test_read_chunk_without_start_raises(self) -> None:
        """Reading without starting raises AudioCaptureError."""
        cap = AudioCapture()
        with pytest.raises(AudioCaptureError, match="not active"):
            await cap.read_chunk()

    @pytest.mark.asyncio
    async def test_start_opens_stream(self) -> None:
        """start() opens a PyAudio stream."""
        mock_pa_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_pa_instance.open.return_value = mock_stream

        mock_pa_mod = MagicMock()
        mock_pa_mod.PyAudio.return_value = mock_pa_instance

        with patch("jarvis.audio.capture._pyaudio", mock_pa_mod):
            cap = AudioCapture(chunk_ms=32)
            await cap.start()

            mock_pa_instance.open.assert_called_once()
            assert cap.is_active

            await cap.stop()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Async context manager starts and stops."""
        mock_pa_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_pa_instance.open.return_value = mock_stream

        mock_pa_mod = MagicMock()
        mock_pa_mod.PyAudio.return_value = mock_pa_instance

        with patch("jarvis.audio.capture._pyaudio", mock_pa_mod):
            async with AudioCapture(chunk_ms=32) as cap:
                assert cap.is_active

    @pytest.mark.asyncio
    async def test_read_chunk_returns_correct_size(self) -> None:
        """read_chunk returns bytes of expected length."""
        mock_pa_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_stream.read.return_value = b"\x00" * 1024
        mock_pa_instance.open.return_value = mock_stream

        mock_pa_mod = MagicMock()
        mock_pa_mod.PyAudio.return_value = mock_pa_instance

        with patch("jarvis.audio.capture._pyaudio", mock_pa_mod):
            async with AudioCapture(chunk_ms=32) as cap:
                data = await cap.read_chunk()
                assert len(data) == 1024

    @pytest.mark.asyncio
    async def test_read_chunk_as_float_returns_float32(self) -> None:
        """read_chunk_as_float returns float32 numpy array."""
        mock_pa_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_stream.read.return_value = b"\x00" * 1024
        mock_pa_instance.open.return_value = mock_stream

        mock_pa_mod = MagicMock()
        mock_pa_mod.PyAudio.return_value = mock_pa_instance

        with patch("jarvis.audio.capture._pyaudio", mock_pa_mod):
            async with AudioCapture(chunk_ms=32) as cap:
                data = await cap.read_chunk_as_float()
                assert data.dtype == np.float32
                assert len(data) == 512

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self) -> None:
        """Calling stop() multiple times doesn't raise."""
        cap = AudioCapture()
        await cap.stop()
        await cap.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_start_without_pyaudio_raises(self) -> None:
        """start() raises AudioCaptureError if pyaudio is not installed."""
        with patch("jarvis.audio.capture._pyaudio", None):
            cap = AudioCapture()
            with pytest.raises(AudioCaptureError, match="pyaudio is not installed"):
                await cap.start()
