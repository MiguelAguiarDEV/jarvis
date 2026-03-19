"""Shared test fixtures for JARVIS."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from jarvis.config import JarvisSettings


@pytest.fixture
def settings() -> JarvisSettings:
    """Default test settings with no real credentials."""
    return JarvisSettings(
        llm_preferred="qwen",
        claude_token="test-token-not-real",
        openai_client_id="test-client-id",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen3.5:9b",
        log_level="DEBUG",
    )


@pytest.fixture
def silence_16k_mono() -> bytes:
    """512 samples of silence as 16-bit PCM bytes (32ms at 16kHz)."""
    return b"\x00" * 1024  # 512 samples * 2 bytes


@pytest.fixture
def tone_16k_mono() -> bytes:
    """512 samples of 440Hz sine wave as 16-bit PCM bytes."""
    t = np.linspace(0, 512 / 16000, 512, endpoint=False, dtype=np.float32)
    sine = np.sin(2 * np.pi * 440 * t)
    pcm = (sine * 32767).astype(np.int16)
    return pcm.tobytes()


@pytest.fixture
def tone_float32() -> np.ndarray:
    """512 samples of 440Hz sine wave as float32 array."""
    t = np.linspace(0, 512 / 16000, 512, endpoint=False, dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t).astype(np.float32)


@pytest.fixture
def mock_pyaudio() -> MagicMock:
    """Mock PyAudio instance with stream."""
    with patch("pyaudio.PyAudio") as mock_pa_class:
        mock_pa = MagicMock()
        mock_pa_class.return_value = mock_pa

        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_stream.read.return_value = b"\x00" * 1024
        mock_pa.open.return_value = mock_stream

        yield mock_pa
