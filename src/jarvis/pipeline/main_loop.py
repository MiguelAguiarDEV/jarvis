"""Main async orchestration pipeline for JARVIS.

State machine: IDLE → LISTENING → TRANSCRIBING → THINKING → SPEAKING → IDLE
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import numpy as np  # noqa: TC002
import structlog

from jarvis.audio.capture import AudioCapture, pcm_bytes_to_float
from jarvis.audio.playback import AudioPlayback
from jarvis.audio.vad import VoiceActivityDetector
from jarvis.audio.wake_word import WakeWordDetector
from jarvis.config import JarvisSettings  # noqa: TC001
from jarvis.llm.base import LLMMessage, LLMProvider, LLMResponse
from jarvis.llm.chatgpt_provider import ChatGPTProvider
from jarvis.llm.claude_provider import ClaudeProvider
from jarvis.llm.qwen_provider import QwenProvider
from jarvis.llm.router import LLMRouter
from jarvis.logging import PipelineTimer, pipeline_state_var, request_id_var
from jarvis.stt.whisper_stt import WhisperSTT
from jarvis.tools.router import ToolRouter
from jarvis.tools.system_info import SystemInfoTool
from jarvis.tts.kokoro_tts import KokoroTTS

if TYPE_CHECKING:
    from jarvis.tools.base import ToolDefinition

log = structlog.get_logger()

# System prompt for JARVIS
SYSTEM_PROMPT = """You are JARVIS, a personal AI voice assistant. You are helpful, concise, and direct.

Rules:
- Keep responses short and conversational — they will be spoken aloud via TTS.
- When you need real-time information (time, date, system info), use the system_info tool.
- Never guess the time or date — always use the tool.
- If you don't know something, say so briefly.
- Respond in the same language the user speaks to you."""

MAX_TOOL_ITERATIONS = 5
MAX_SILENCE_SEC = 10.0  # Max time to wait for speech after wake word


class PipelineState(StrEnum):
    """Pipeline state machine states."""

    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"


class JarvisPipeline:
    """Main async orchestration pipeline.

    Single-threaded async loop. Blocking operations (STT, TTS, model load)
    run in the default executor (ThreadPoolExecutor).
    """

    def __init__(
        self,
        settings: JarvisSettings,
        event_callback: Callable[..., Any] | None = None,
    ) -> None:
        self._settings = settings
        self._state = PipelineState.IDLE
        self._shutdown_event = asyncio.Event()
        self._event_callback = event_callback

        # Components — initialized in initialize()
        self._capture: AudioCapture | None = None
        self._playback: AudioPlayback | None = None
        self._wake_word: WakeWordDetector | None = None
        self._vad: VoiceActivityDetector | None = None
        self._stt: WhisperSTT | None = None
        self._tts: KokoroTTS | None = None
        self._llm_router: LLMRouter | None = None
        self._tool_router: ToolRouter | None = None

    @property
    def state(self) -> PipelineState:
        return self._state

    def _emit(self, event_type: str, **kwargs: Any) -> None:
        """Emit event to callback if registered."""
        if self._event_callback is not None:
            try:
                self._event_callback(event_type, **kwargs)
            except Exception:
                log.exception("pipeline.event_callback_error", event_type=event_type)

    def _set_state(self, state: PipelineState) -> None:
        old = self._state
        self._state = state
        pipeline_state_var.set(state.value)
        log.info("pipeline.state_change", old=old.value, new=state.value)
        self._emit("state_change", old=old, new=state, request_id=request_id_var.get())

    async def initialize(self) -> None:
        """Load all components. Called once at startup.

        Loads (in parallel where possible):
        - Wake word model (CPU, ~50MB)
        - VAD model (CPU, ~2MB)
        - TTS model (CPU, ~300MB)
        - LLM provider health checks

        Does NOT load STT model (on-demand VRAM).
        """
        log.info("pipeline.initializing")
        start = time.perf_counter()

        # Create components (instant, no I/O)
        self._capture = AudioCapture(chunk_ms=32)
        self._playback = AudioPlayback(sample_rate=24_000)
        self._wake_word = WakeWordDetector(
            wake_word=self._settings.wake_word.replace(" ", "_"),
            threshold=self._settings.wake_threshold,
        )
        self._vad = VoiceActivityDetector(
            threshold=self._settings.vad_threshold,
            min_silence_ms=self._settings.vad_silence_ms,
        )
        self._stt = WhisperSTT(
            model_name=self._settings.stt_model,
            device=self._settings.stt_device,
            compute_type=self._settings.stt_compute_type,
        )
        self._tts = KokoroTTS(
            model_path=self._settings.tts_model_path,
            voices_path=self._settings.tts_voices_path,
            default_voice=self._settings.tts_voice,
            default_speed=self._settings.tts_speed,
        )

        # Setup LLM providers + tools (instant)
        self._llm_router = self._create_llm_router()
        self._tool_router = ToolRouter()
        self._tool_router.register(SystemInfoTool())

        # Load components one by one with progress events
        await self._init_component("Wake Word", self._wake_word.load)
        await self._init_component("VAD", self._vad.load)
        await self._init_component("TTS", self._tts.load)
        await self._init_component("Microphone", self._capture.start)
        await self._init_component("Speaker", self._playback.start)

        # Health check LLM providers
        self._emit("init_progress", component="LLM Providers", status="loading")
        health = await self._llm_router.health_check()
        for provider, healthy in health.items():
            status = "ok" if healthy else "offline"
            self._emit("init_progress", component=f"  {provider}", status=status)
            log.info("pipeline.llm_health", provider=provider, healthy=healthy)

        elapsed = time.perf_counter() - start
        log.info(
            "pipeline.initialized",
            elapsed_ms=round(elapsed * 1000, 1),
            tools=self._tool_router.tool_count,
            llm_preferred=self._settings.llm_preferred,
        )
        self._emit(
            "ready",
            provider_health=health,
            tool_count=self._tool_router.tool_count,
        )

    async def _init_component(self, name: str, load_fn: Any) -> None:
        """Load a single component with progress events."""
        self._emit("init_progress", component=name, status="loading")
        try:
            await load_fn()
            self._emit("init_progress", component=name, status="ok")
        except Exception as e:
            self._emit("init_progress", component=name, status="failed")
            log.error("pipeline.component_load_failed", component=name, error=str(e))
            raise

    def _create_llm_router(self) -> LLMRouter:
        """Create LLM router with configured providers."""
        providers: dict[str, LLMProvider] = {}

        if self._settings.claude_token.get_secret_value():
            providers["claude"] = ClaudeProvider(
                api_key=self._settings.claude_token.get_secret_value()
            )
            log.info("pipeline.llm_provider_configured", provider="claude")

        if self._settings.openai_access_token.get_secret_value():
            providers["chatgpt"] = ChatGPTProvider(
                access_token=self._settings.openai_access_token.get_secret_value()
            )
            log.info("pipeline.llm_provider_configured", provider="chatgpt")

        providers["qwen"] = QwenProvider(
            base_url=self._settings.ollama_base_url,
            model=self._settings.ollama_model,
        )
        log.info("pipeline.llm_provider_configured", provider="qwen")

        return LLMRouter(
            providers=providers,
            priority=["claude", "chatgpt", "qwen"],
        )

    async def run(self) -> None:
        """Main loop. Runs until shutdown is requested.

        Loop:
        1. Capture audio chunk
        2. Feed to wake word detector
        3. On wake → listen via VAD → accumulate speech
        4. Transcribe → LLM → TTS → playback
        5. Return to idle
        """
        log.info("pipeline.running")
        self._set_state(PipelineState.IDLE)

        try:
            while not self._shutdown_event.is_set():
                try:
                    await self._idle_loop()
                except asyncio.CancelledError:
                    break
                except Exception:
                    log.exception("pipeline.loop_error")
                    # Brief pause before retrying to avoid tight error loops
                    await asyncio.sleep(0.5)
                    self._set_state(PipelineState.IDLE)
        finally:
            log.info("pipeline.stopped")

    async def _idle_loop(self) -> None:
        """Listen for wake word, then process one conversation turn."""
        if self._capture is None or self._wake_word is None:
            msg = "Pipeline not initialized"
            raise RuntimeError(msg)

        # Read audio chunk
        chunk_bytes = await self._capture.read_chunk()

        # Feed to wake word detector
        scores = self._wake_word.process_frame(chunk_bytes)
        if not self._wake_word.detected(scores):
            return

        # Wake word detected!
        request_id = uuid.uuid4().hex[:12]
        request_id_var.set(request_id)
        log.info(
            "pipeline.wake_detected",
            score=scores.get(self._wake_word.wake_word, 0.0),
        )
        self._wake_word.reset()

        conversation_start = time.perf_counter()
        try:
            # Listen for speech
            audio = await self._listen_for_speech()
            if audio is None or len(audio) < 1600:  # Less than 100ms
                log.warning("pipeline.no_speech_detected")
                self._set_state(PipelineState.IDLE)
                return

            # Transcribe
            text = await self._transcribe(audio)
            if not text.strip():
                log.warning("pipeline.empty_transcription")
                self._set_state(PipelineState.IDLE)
                return

            # Think (LLM + tools)
            response_text, provider, model, tool_names = await self._think(text)
            if not response_text:
                log.warning("pipeline.empty_response")
                self._set_state(PipelineState.IDLE)
                return

            # Speak
            await self._speak(response_text)

            # Emit conversation complete
            elapsed_ms = (time.perf_counter() - conversation_start) * 1000
            self._emit(
                "conversation_complete",
                user_text=text,
                response_text=response_text,
                provider=provider,
                model=model,
                elapsed_ms=round(elapsed_ms, 1),
                tool_names=tool_names,
                request_id=request_id,
            )

        except Exception:
            log.exception("pipeline.conversation_error")
            self._emit("error", error="Conversation failed", stage="conversation")
        finally:
            self._set_state(PipelineState.IDLE)
            request_id_var.set("")

    async def _listen_for_speech(self) -> np.ndarray | None:
        """After wake detection: listen via VAD, return accumulated audio."""
        if self._capture is None or self._vad is None:
            return None

        self._set_state(PipelineState.LISTENING)
        self._vad.reset()

        audio_buffer = bytearray()
        speech_started = False
        listen_start = time.perf_counter()

        while not self._shutdown_event.is_set():
            # Timeout check
            elapsed = time.perf_counter() - listen_start
            if elapsed > MAX_SILENCE_SEC:
                log.warning("pipeline.listen_timeout", elapsed_sec=round(elapsed, 1))
                break

            chunk_bytes = await self._capture.read_chunk()
            chunk_float = pcm_bytes_to_float(chunk_bytes)

            event = self._vad.process_chunk(chunk_float)

            if event is not None and event.type == "start":
                speech_started = True
                log.debug("pipeline.speech_start", timestamp=event.timestamp_sec)

            if speech_started:
                audio_buffer.extend(chunk_bytes)

            if event is not None and event.type == "end" and speech_started:
                log.info(
                    "pipeline.speech_end",
                    timestamp=event.timestamp_sec,
                    audio_bytes=len(audio_buffer),
                    duration_ms=round(len(audio_buffer) / 32, 1),  # 16kHz * 2 bytes = 32 bytes/ms
                )
                break

        if not audio_buffer:
            return None

        return pcm_bytes_to_float(bytes(audio_buffer))

    async def _transcribe(self, audio: np.ndarray) -> str:
        """STT: load model → transcribe → unload model."""
        if self._stt is None:
            return ""

        self._set_state(PipelineState.TRANSCRIBING)

        async with PipelineTimer("stt.transcribe", audio_samples=len(audio)):
            result = await self._stt.transcribe_and_unload(audio)

        log.info(
            "pipeline.transcription",
            text=result.text,
            language=result.language,
            language_prob=round(result.language_probability, 2),
            duration_sec=round(result.duration_sec, 2),
        )
        return result.text

    async def _think(self, user_text: str) -> tuple[str | None, str, str, list[str]]:
        """LLM: send text → handle tool calls → return final response.

        Returns:
            Tuple of (response_text, provider, model, tool_names_used).
        """
        if self._llm_router is None or self._tool_router is None:
            return None, "", "", []

        self._set_state(PipelineState.THINKING)

        messages: list[LLMMessage] = [
            LLMMessage(role="user", content=user_text),
        ]
        tool_defs = self._tool_router.get_definitions()
        tool_names_used: list[str] = []

        async with PipelineTimer("llm.complete", user_text_length=len(user_text)):
            response = await self._llm_router.complete(
                messages=messages,
                tools=tool_defs,
                system_prompt=SYSTEM_PROMPT,
                preferred_provider=self._settings.llm_preferred,
            )

        log.info(
            "pipeline.llm_response",
            provider=response.provider,
            model=response.model,
            finish_reason=response.finish_reason,
            has_tool_calls=len(response.tool_calls) > 0,
            usage=response.usage,
        )

        # Handle tool call loop
        if response.tool_calls:
            tool_names_used = [tc.name for tc in response.tool_calls]
            response = await self._tool_loop(messages, response, tool_defs)
            # Collect all tool names from subsequent iterations
            for msg in messages:
                for tc in msg.tool_calls:
                    if tc.name not in tool_names_used:
                        tool_names_used.append(tc.name)

        return response.content, response.provider, response.model, tool_names_used

    async def _tool_loop(
        self,
        messages: list[LLMMessage],
        response: LLMResponse,
        tool_defs: list[ToolDefinition],
    ) -> LLMResponse:
        """Execute tool calls and re-query LLM until no more tool calls.

        Max MAX_TOOL_ITERATIONS iterations to prevent infinite loops.
        """
        if self._llm_router is None or self._tool_router is None:
            return response

        for iteration in range(MAX_TOOL_ITERATIONS):
            if not response.tool_calls:
                break

            log.info(
                "pipeline.tool_loop",
                iteration=iteration + 1,
                tool_calls=[tc.name for tc in response.tool_calls],
            )

            # Add assistant message with tool calls
            messages.append(
                LLMMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )

            # Execute each tool call
            for tc in response.tool_calls:
                async with PipelineTimer("tool.execute", tool=tc.name):
                    try:
                        result = await self._tool_router.execute(tc.name, tc.arguments)
                        result_content = json.dumps(result.data)
                    except Exception as e:
                        log.error("pipeline.tool_error", tool=tc.name, error=str(e))
                        result_content = json.dumps({"error": str(e)})

                messages.append(
                    LLMMessage(
                        role="tool",
                        content=result_content,
                        tool_call_id=tc.id,
                    )
                )

            # Re-query LLM with tool results
            async with PipelineTimer("llm.complete_with_tools", iteration=iteration + 1):
                response = await self._llm_router.complete(
                    messages=messages,
                    tools=tool_defs,
                    system_prompt=SYSTEM_PROMPT,
                    preferred_provider=self._settings.llm_preferred,
                )

            log.info(
                "pipeline.llm_response_after_tools",
                provider=response.provider,
                finish_reason=response.finish_reason,
                iteration=iteration + 1,
            )

        if response.tool_calls:
            log.warning("pipeline.tool_loop_max_iterations", max=MAX_TOOL_ITERATIONS)

        return response

    async def _speak(self, text: str) -> None:
        """TTS: synthesize text → play audio."""
        if self._tts is None or self._playback is None:
            return

        self._set_state(PipelineState.SPEAKING)

        async with PipelineTimer("tts.synthesize", text_length=len(text)):
            result = await self._tts.synthesize(text)

        log.info(
            "pipeline.tts_result",
            audio_samples=len(result.audio),
            duration_sec=round(len(result.audio) / result.sample_rate, 2),
            sample_rate=result.sample_rate,
        )

        async with PipelineTimer("audio.playback"):
            await self._playback.play(result.audio, result.sample_rate)

    async def shutdown(self) -> None:
        """Graceful shutdown. Release all resources."""
        log.info("pipeline.shutting_down")
        self._shutdown_event.set()

        if self._capture:
            await self._capture.stop()
        if self._playback:
            await self._playback.stop()
        if self._wake_word:
            await self._wake_word.unload()
        if self._vad:
            await self._vad.unload()
        if self._stt:
            await self._stt.unload_model()
        if self._tts:
            await self._tts.unload()

        log.info("pipeline.shutdown_complete")
