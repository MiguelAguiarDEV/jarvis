"""Tests for audio playback module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from jarvis.audio.playback import AudioPlayback, AudioPlaybackError, float_to_pcm_bytes


class TestFloatToPcmBytes:
    """Test float-to-PCM conversion utility."""

    def test_silence_converts_to_zero_bytes(self) -> None:
        """Zero float array converts to zero PCM bytes."""
        silence = np.zeros(512, dtype=np.float32)
        result = float_to_pcm_bytes(silence)
        assert len(result) == 1024  # 512 samples * 2 bytes
        assert result == b"\x00" * 1024

    def test_positive_one_converts_to_max_int16(self) -> None:
        """1.0 float converts to 32767 int16."""
        one = np.array([1.0], dtype=np.float32)
        result = float_to_pcm_bytes(one)
        value = np.frombuffer(result, dtype=np.int16)[0]
        assert value == 32767

    def test_negative_one_converts_to_min_int16(self) -> None:
        """-1.0 float converts to -32767 int16."""
        neg_one = np.array([-1.0], dtype=np.float32)
        result = float_to_pcm_bytes(neg_one)
        value = np.frombuffer(result, dtype=np.int16)[0]
        assert value == -32767

    def test_clipping_above_one(self) -> None:
        """Values above 1.0 are clipped."""
        over = np.array([2.0], dtype=np.float32)
        result = float_to_pcm_bytes(over)
        value = np.frombuffer(result, dtype=np.int16)[0]
        assert value == 32767

    def test_clipping_below_minus_one(self) -> None:
        """Values below -1.0 are clipped."""
        under = np.array([-2.0], dtype=np.float32)
        result = float_to_pcm_bytes(under)
        value = np.frombuffer(result, dtype=np.int16)[0]
        assert value == -32767


class TestAudioPlayback:
    """Test AudioPlayback initialization and playback."""

    def test_default_sample_rate(self) -> None:
        """Default sample rate is 24kHz (Kokoro output)."""
        pb = AudioPlayback()
        assert pb.sample_rate == 24_000

    def test_custom_sample_rate(self) -> None:
        """Custom sample rate is accepted."""
        pb = AudioPlayback(sample_rate=16_000)
        assert pb.sample_rate == 16_000

    @pytest.mark.asyncio
    async def test_play_without_start_raises(self) -> None:
        """Playing without starting raises AudioPlaybackError."""
        pb = AudioPlayback()
        audio = np.zeros(512, dtype=np.float32)
        with pytest.raises(AudioPlaybackError, match="not started"):
            await pb.play(audio)

    @pytest.mark.asyncio
    async def test_start_initializes_pyaudio(self) -> None:
        """start() creates a PyAudio instance."""
        mock_pa_instance = MagicMock()
        mock_pa_mod = MagicMock()
        mock_pa_mod.PyAudio.return_value = mock_pa_instance

        with patch("jarvis.audio.playback._pyaudio", mock_pa_mod):
            pb = AudioPlayback()
            await pb.start()
            mock_pa_mod.PyAudio.assert_called_once()
            await pb.stop()

    @pytest.mark.asyncio
    async def test_play_opens_and_closes_stream(self) -> None:
        """play() opens a stream, writes data, and closes it."""
        mock_pa_instance = MagicMock()
        mock_stream = MagicMock()
        mock_pa_instance.open.return_value = mock_stream

        mock_pa_mod = MagicMock()
        mock_pa_mod.PyAudio.return_value = mock_pa_instance

        with patch("jarvis.audio.playback._pyaudio", mock_pa_mod):
            async with AudioPlayback(sample_rate=24_000) as pb:
                audio = np.zeros(512, dtype=np.float32)
                await pb.play(audio)

            mock_pa_instance.open.assert_called_once()
            mock_stream.write.assert_called_once()
            mock_stream.stop_stream.assert_called_once()
            mock_stream.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_play_with_custom_sample_rate(self) -> None:
        """play() uses provided sample rate over default."""
        mock_pa_instance = MagicMock()
        mock_stream = MagicMock()
        mock_pa_instance.open.return_value = mock_stream

        mock_pa_mod = MagicMock()
        mock_pa_mod.PyAudio.return_value = mock_pa_instance

        with patch("jarvis.audio.playback._pyaudio", mock_pa_mod):
            async with AudioPlayback(sample_rate=24_000) as pb:
                audio = np.zeros(512, dtype=np.float32)
                await pb.play(audio, sample_rate=16_000)

            call_kwargs = mock_pa_instance.open.call_args
            assert call_kwargs[1]["rate"] == 16_000

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self) -> None:
        """Calling stop() multiple times doesn't raise."""
        pb = AudioPlayback()
        await pb.stop()
        await pb.stop()

    @pytest.mark.asyncio
    async def test_start_without_pyaudio_raises(self) -> None:
        """start() raises AudioPlaybackError if pyaudio is not installed."""
        with patch("jarvis.audio.playback._pyaudio", None):
            pb = AudioPlayback()
            with pytest.raises(AudioPlaybackError, match="pyaudio is not installed"):
                await pb.start()
