"""JARVIS configuration via environment variables and .env file."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class JarvisSettings(BaseSettings):
    """All configuration loaded from environment variables and .env file.

    Credentials are loaded here and passed to components at init time.
    They are NEVER serialized into LLM messages or tool outputs.
    """

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM ---
    llm_preferred: Literal["claude", "chatgpt", "qwen"] = "claude"
    claude_token: str = ""
    openai_client_id: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"

    # --- STT ---
    stt_model: str = "large-v3-turbo"
    stt_device: str = "cuda"
    stt_compute_type: str = "float16"

    # --- TTS ---
    tts_model_path: str = "models/kokoro-v1.0.onnx"
    tts_voices_path: str = "models/voices-v1.0.bin"
    tts_voice: str = "af_sarah"
    tts_speed: float = Field(default=1.0, ge=0.5, le=2.0)

    # --- Wake Word ---
    wake_word: str = "hey jarvis"
    wake_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    # --- VAD ---
    vad_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    vad_silence_ms: int = Field(default=300, ge=50, le=5000)

    # --- General ---
    log_level: str = "INFO"

    # --- OAuth tokens (managed by auth flow, not user-edited) ---
    openai_access_token: str = ""
    openai_refresh_token: str = ""

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            msg = f"Invalid log level: {v}. Must be one of {valid}"
            raise ValueError(msg)
        return upper

    @field_validator("tts_model_path", "tts_voices_path")
    @classmethod
    def validate_path_format(cls, v: str) -> str:
        """Validate path is not empty. Existence checked at runtime."""
        if not v.strip():
            msg = "Path cannot be empty"
            raise ValueError(msg)
        return v

    @property
    def tts_model_resolved(self) -> Path:
        """Resolve TTS model path relative to CWD."""
        return Path(self.tts_model_path).resolve()

    @property
    def tts_voices_resolved(self) -> Path:
        """Resolve TTS voices path relative to CWD."""
        return Path(self.tts_voices_path).resolve()
