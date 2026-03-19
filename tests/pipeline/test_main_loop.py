"""Tests for main pipeline loop."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from jarvis.config import JarvisSettings
from jarvis.llm.base import LLMMessage, LLMResponse, ToolCall
from jarvis.pipeline.main_loop import JarvisPipeline, PipelineState
from jarvis.tools.base import ToolResult


def _make_settings(**overrides: object) -> JarvisSettings:
    """Create test settings."""
    defaults = {
        "llm_preferred": "qwen",
        "claude_token": "",
        "openai_access_token": "",
        "ollama_base_url": "http://localhost:11434",
        "ollama_model": "qwen3.5:9b",
        "stt_model": "tiny",
        "stt_device": "cpu",
        "stt_compute_type": "int8",
        "tts_model_path": "models/kokoro-v1.0.onnx",
        "tts_voices_path": "models/voices-v1.0.bin",
        "wake_word": "hey jarvis",
        "log_level": "DEBUG",
    }
    defaults.update(overrides)  # type: ignore[arg-type]
    return JarvisSettings(_env_file=None, **defaults)  # type: ignore[call-arg]


class TestPipelineState:
    def test_states_are_strings(self) -> None:
        assert PipelineState.IDLE == "idle"
        assert PipelineState.LISTENING == "listening"
        assert PipelineState.TRANSCRIBING == "transcribing"
        assert PipelineState.THINKING == "thinking"
        assert PipelineState.SPEAKING == "speaking"


class TestJarvisPipeline:
    def test_initial_state(self) -> None:
        settings = _make_settings()
        pipeline = JarvisPipeline(settings)
        assert pipeline.state == PipelineState.IDLE

    @pytest.mark.asyncio
    async def test_shutdown_sets_event(self) -> None:
        settings = _make_settings()
        pipeline = JarvisPipeline(settings)
        assert not pipeline._shutdown_event.is_set()
        await pipeline.shutdown()
        assert pipeline._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_create_llm_router_qwen_only(self) -> None:
        """With no cloud tokens, only qwen is configured."""
        settings = _make_settings(claude_token="", openai_access_token="")
        pipeline = JarvisPipeline(settings)
        router = pipeline._create_llm_router()
        assert "qwen" in router.providers
        assert "claude" not in router.providers
        assert "chatgpt" not in router.providers

    @pytest.mark.asyncio
    async def test_create_llm_router_all_providers(self) -> None:
        """With all tokens, all providers are configured."""
        settings = _make_settings(
            claude_token="test-claude-token",
            openai_access_token="test-openai-token",
        )
        pipeline = JarvisPipeline(settings)
        router = pipeline._create_llm_router()
        assert "claude" in router.providers
        assert "chatgpt" in router.providers
        assert "qwen" in router.providers

    @pytest.mark.asyncio
    async def test_think_with_tool_call(self) -> None:
        """_think handles tool calls correctly."""
        settings = _make_settings()
        pipeline = JarvisPipeline(settings)

        # Mock LLM router
        mock_router = MagicMock()

        # First response: tool call
        tool_call_response = LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="tc_1", name="system_info", arguments={"fields": ["time"]})],
            provider="qwen",
            model="qwen3.5:9b",
            usage={"input_tokens": 10, "output_tokens": 5},
            finish_reason="tool_use",
        )
        # Second response: final text
        final_response = LLMResponse(
            content="The current time is 14:30:00.",
            tool_calls=[],
            provider="qwen",
            model="qwen3.5:9b",
            usage={"input_tokens": 20, "output_tokens": 10},
            finish_reason="stop",
        )
        mock_router.complete = AsyncMock(side_effect=[tool_call_response, final_response])
        pipeline._llm_router = mock_router

        # Mock tool router
        mock_tool_router = MagicMock()
        mock_tool_router.get_definitions.return_value = []
        mock_tool_router.execute = AsyncMock(
            return_value=ToolResult(
                tool_name="system_info",
                success=True,
                data={"time": "14:30:00"},
            )
        )
        pipeline._tool_router = mock_tool_router

        result = await pipeline._think("What time is it?")
        assert result == "The current time is 14:30:00."
        assert mock_router.complete.call_count == 2
        mock_tool_router.execute.assert_called_once_with("system_info", {"fields": ["time"]})

    @pytest.mark.asyncio
    async def test_think_no_tool_calls(self) -> None:
        """_think returns content directly when no tool calls."""
        settings = _make_settings()
        pipeline = JarvisPipeline(settings)

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(
            return_value=LLMResponse(
                content="Hello! How can I help?",
                tool_calls=[],
                provider="qwen",
                model="qwen3.5:9b",
                usage={"input_tokens": 5, "output_tokens": 8},
                finish_reason="stop",
            )
        )
        pipeline._llm_router = mock_router

        mock_tool_router = MagicMock()
        mock_tool_router.get_definitions.return_value = []
        pipeline._tool_router = mock_tool_router

        result = await pipeline._think("Hello")
        assert result == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_speak_synthesizes_and_plays(self) -> None:
        """_speak calls TTS then playback."""
        settings = _make_settings()
        pipeline = JarvisPipeline(settings)

        audio = np.zeros(24000, dtype=np.float32)
        mock_tts = MagicMock()
        mock_tts.synthesize = AsyncMock(return_value=MagicMock(audio=audio, sample_rate=24000))
        pipeline._tts = mock_tts

        mock_playback = MagicMock()
        mock_playback.play = AsyncMock()
        pipeline._playback = mock_playback

        await pipeline._speak("Hello world")

        mock_tts.synthesize.assert_called_once_with("Hello world")
        mock_playback.play.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_calls_stt(self) -> None:
        """_transcribe loads STT, transcribes, and unloads."""
        settings = _make_settings()
        pipeline = JarvisPipeline(settings)

        mock_stt = MagicMock()
        mock_stt.transcribe_and_unload = AsyncMock(
            return_value=MagicMock(
                text="hello world",
                language="en",
                language_probability=0.95,
                duration_sec=1.5,
            )
        )
        pipeline._stt = mock_stt

        audio = np.zeros(16000, dtype=np.float32)
        result = await pipeline._transcribe(audio)

        assert result == "hello world"
        mock_stt.transcribe_and_unload.assert_called_once()

    @pytest.mark.asyncio
    async def test_listen_returns_none_on_timeout(self) -> None:
        """_listen_for_speech returns None if no speech within timeout."""
        settings = _make_settings()
        pipeline = JarvisPipeline(settings)

        # Mock capture that returns silence
        mock_capture = MagicMock()
        mock_capture.read_chunk = AsyncMock(return_value=b"\x00" * 1024)
        pipeline._capture = mock_capture

        # Mock VAD that never detects speech
        mock_vad = MagicMock()
        mock_vad.reset.return_value = None
        mock_vad.process_chunk.return_value = None
        pipeline._vad = mock_vad

        # Patch MAX_SILENCE_SEC to make test fast
        with patch("jarvis.pipeline.main_loop.MAX_SILENCE_SEC", 0.1):
            result = await pipeline._listen_for_speech()

        assert result is None

    @pytest.mark.asyncio
    async def test_tool_loop_max_iterations(self) -> None:
        """Tool loop stops after MAX_TOOL_ITERATIONS."""
        settings = _make_settings()
        pipeline = JarvisPipeline(settings)

        # LLM always returns tool calls (infinite loop scenario)
        infinite_response = LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="tc_1", name="system_info", arguments={"fields": ["time"]})],
            provider="qwen",
            model="qwen3.5:9b",
            usage={"input_tokens": 10, "output_tokens": 5},
            finish_reason="tool_use",
        )
        mock_router = MagicMock()
        mock_router.complete = AsyncMock(return_value=infinite_response)
        pipeline._llm_router = mock_router

        mock_tool_router = MagicMock()
        mock_tool_router.execute = AsyncMock(
            return_value=ToolResult(tool_name="system_info", success=True, data={"time": "12:00"})
        )
        pipeline._tool_router = mock_tool_router

        messages: list[LLMMessage] = [LLMMessage(role="user", content="test")]
        await pipeline._tool_loop(messages, infinite_response, [])

        # Should stop after MAX_TOOL_ITERATIONS (5)
        assert mock_router.complete.call_count == 5
