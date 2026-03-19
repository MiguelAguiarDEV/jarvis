"""Tests for JARVIS configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from jarvis.config import JarvisSettings


class TestJarvisSettings:
    """Test configuration loading and validation."""

    def test_default_values(self) -> None:
        """Settings load with sensible defaults when no env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            settings = JarvisSettings(_env_file=None)  # type: ignore[call-arg]

        assert settings.llm_preferred == "claude"
        assert settings.stt_model == "large-v3-turbo"
        assert settings.stt_device == "cuda"
        assert settings.tts_voice == "af_sarah"
        assert settings.tts_speed == 1.0
        assert settings.wake_word == "hey jarvis"
        assert settings.wake_threshold == 0.5
        assert settings.vad_threshold == 0.5
        assert settings.vad_silence_ms == 300
        assert settings.log_level == "INFO"

    def test_env_override(self) -> None:
        """Environment variables override defaults."""
        env = {
            "JARVIS_LLM_PREFERRED": "qwen",
            "JARVIS_STT_DEVICE": "cpu",
            "JARVIS_TTS_SPEED": "1.5",
            "JARVIS_LOG_LEVEL": "debug",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = JarvisSettings(_env_file=None)  # type: ignore[call-arg]

        assert settings.llm_preferred == "qwen"
        assert settings.stt_device == "cpu"
        assert settings.tts_speed == 1.5
        assert settings.log_level == "DEBUG"

    def test_invalid_log_level_raises(self) -> None:
        """Invalid log level raises ValueError."""
        env = {"JARVIS_LOG_LEVEL": "INVALID"}
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="Invalid log level"),
        ):
            JarvisSettings(_env_file=None)  # type: ignore[call-arg]

    def test_invalid_llm_preferred_raises(self) -> None:
        """Invalid LLM provider raises ValueError."""
        env = {"JARVIS_LLM_PREFERRED": "gpt5"}
        with patch.dict(os.environ, env, clear=True), pytest.raises(ValueError):
            JarvisSettings(_env_file=None)  # type: ignore[call-arg]

    def test_tts_speed_bounds(self) -> None:
        """TTS speed must be between 0.5 and 2.0."""
        env = {"JARVIS_TTS_SPEED": "3.0"}
        with patch.dict(os.environ, env, clear=True), pytest.raises(ValueError):
            JarvisSettings(_env_file=None)  # type: ignore[call-arg]

    def test_tts_speed_too_low(self) -> None:
        """TTS speed below 0.5 raises."""
        env = {"JARVIS_TTS_SPEED": "0.1"}
        with patch.dict(os.environ, env, clear=True), pytest.raises(ValueError):
            JarvisSettings(_env_file=None)  # type: ignore[call-arg]

    def test_wake_threshold_bounds(self) -> None:
        """Wake threshold must be between 0.0 and 1.0."""
        env = {"JARVIS_WAKE_THRESHOLD": "1.5"}
        with patch.dict(os.environ, env, clear=True), pytest.raises(ValueError):
            JarvisSettings(_env_file=None)  # type: ignore[call-arg]

    def test_vad_silence_ms_bounds(self) -> None:
        """VAD silence must be between 50 and 5000."""
        env = {"JARVIS_VAD_SILENCE_MS": "10"}
        with patch.dict(os.environ, env, clear=True), pytest.raises(ValueError):
            JarvisSettings(_env_file=None)  # type: ignore[call-arg]

    def test_empty_tts_path_raises(self) -> None:
        """Empty TTS model path raises."""
        env = {"JARVIS_TTS_MODEL_PATH": "  "}
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="Path cannot be empty"),
        ):
            JarvisSettings(_env_file=None)  # type: ignore[call-arg]

    def test_tts_resolved_paths(self) -> None:
        """Resolved paths return absolute Path objects."""
        with patch.dict(os.environ, {}, clear=True):
            settings = JarvisSettings(_env_file=None)  # type: ignore[call-arg]

        assert settings.tts_model_resolved.is_absolute()
        assert settings.tts_voices_resolved.is_absolute()

    def test_credentials_default_to_empty(self) -> None:
        """Credential fields default to empty SecretStr (not None)."""
        with patch.dict(os.environ, {}, clear=True):
            settings = JarvisSettings(_env_file=None)  # type: ignore[call-arg]

        assert settings.claude_token.get_secret_value() == ""
        assert settings.openai_client_id == ""
        assert settings.openai_access_token.get_secret_value() == ""
        assert settings.openai_refresh_token.get_secret_value() == ""

    def test_secret_str_not_leaked_in_repr(self) -> None:
        """SecretStr fields show '**********' in repr, not actual values."""
        env = {"JARVIS_CLAUDE_TOKEN": "super-secret-token"}
        with patch.dict(os.environ, env, clear=True):
            settings = JarvisSettings(_env_file=None)  # type: ignore[call-arg]

        settings_repr = repr(settings)
        assert "super-secret-token" not in settings_repr
        assert "**********" in settings_repr
