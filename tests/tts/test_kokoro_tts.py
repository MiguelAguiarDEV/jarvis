"""Tests for Kokoro TTS module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from jarvis.tts.kokoro_tts import KokoroTTS, TTSError, TTSResult


class TestTTSResult:
    """Test TTSResult dataclass."""

    def test_creation(self) -> None:
        audio = np.zeros(24000, dtype=np.float32)
        result = TTSResult(audio=audio, sample_rate=24000)
        assert result.sample_rate == 24000
        assert len(result.audio) == 24000

    def test_frozen(self) -> None:
        audio = np.zeros(100, dtype=np.float32)
        result = TTSResult(audio=audio, sample_rate=24000)
        with pytest.raises(AttributeError):
            result.sample_rate = 16000  # type: ignore[misc]


class TestKokoroTTS:
    """Test KokoroTTS engine."""

    def test_default_params(self) -> None:
        tts = KokoroTTS()
        assert tts.default_voice == "af_sarah"
        assert tts.default_speed == 1.0
        assert not tts.is_loaded

    def test_custom_params(self) -> None:
        tts = KokoroTTS(
            model_path="custom.onnx",
            voices_path="custom.bin",
            default_voice="bf_emma",
            default_speed=1.5,
        )
        assert tts.default_voice == "bf_emma"
        assert tts.default_speed == 1.5

    @pytest.mark.asyncio
    async def test_load(self) -> None:
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah", "bf_emma"]

        with patch("jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro):
            tts = KokoroTTS()
            await tts.load()
            assert tts.is_loaded

    @pytest.mark.asyncio
    async def test_load_is_idempotent(self) -> None:
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah"]

        with patch(
            "jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro
        ) as load_mock:
            tts = KokoroTTS()
            await tts.load()
            await tts.load()
            load_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_file_not_found(self) -> None:
        with patch(
            "jarvis.tts.kokoro_tts.KokoroTTS._load_sync",
            side_effect=FileNotFoundError("model.onnx"),
        ):
            tts = KokoroTTS()
            with pytest.raises(TTSError, match="not found"):
                await tts.load()

    @pytest.mark.asyncio
    async def test_load_generic_failure(self) -> None:
        with patch(
            "jarvis.tts.kokoro_tts.KokoroTTS._load_sync",
            side_effect=RuntimeError("onnx error"),
        ):
            tts = KokoroTTS()
            with pytest.raises(TTSError, match="Failed to load"):
                await tts.load()
            assert not tts.is_loaded

    @pytest.mark.asyncio
    async def test_synthesize_without_load_raises(self) -> None:
        tts = KokoroTTS()
        with pytest.raises(TTSError, match="not loaded"):
            await tts.synthesize("hello")

    @pytest.mark.asyncio
    async def test_synthesize_empty_text_raises(self) -> None:
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah"]

        with patch("jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro):
            tts = KokoroTTS()
            await tts.load()
            with pytest.raises(TTSError, match="empty text"):
                await tts.synthesize("")

    @pytest.mark.asyncio
    async def test_synthesize_whitespace_only_raises(self) -> None:
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah"]

        with patch("jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro):
            tts = KokoroTTS()
            await tts.load()
            with pytest.raises(TTSError, match="empty text"):
                await tts.synthesize("   ")

    @pytest.mark.asyncio
    async def test_synthesize_returns_tts_result(self) -> None:
        audio = np.random.randn(24000).astype(np.float32)
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah"]
        mock_kokoro.create.return_value = (audio, 24000)

        with patch("jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro):
            tts = KokoroTTS()
            await tts.load()
            result = await tts.synthesize("hello world")

            assert isinstance(result, TTSResult)
            assert result.sample_rate == 24000
            assert len(result.audio) == 24000

    @pytest.mark.asyncio
    async def test_synthesize_uses_default_voice(self) -> None:
        audio = np.zeros(100, dtype=np.float32)
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah"]
        mock_kokoro.create.return_value = (audio, 24000)

        with patch("jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro):
            tts = KokoroTTS(default_voice="af_sarah", default_speed=1.2)
            await tts.load()
            await tts.synthesize("test")

            mock_kokoro.create.assert_called_once_with(
                "test", voice="af_sarah", speed=1.2, lang="en-us"
            )

    @pytest.mark.asyncio
    async def test_synthesize_overrides_voice_and_speed(self) -> None:
        audio = np.zeros(100, dtype=np.float32)
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah", "bf_emma"]
        mock_kokoro.create.return_value = (audio, 24000)

        with patch("jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro):
            tts = KokoroTTS(default_voice="af_sarah", default_speed=1.0)
            await tts.load()
            await tts.synthesize("test", voice="bf_emma", speed=0.8, lang="en-gb")

            mock_kokoro.create.assert_called_once_with(
                "test", voice="bf_emma", speed=0.8, lang="en-gb"
            )

    @pytest.mark.asyncio
    async def test_synthesize_failure_raises_tts_error(self) -> None:
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah"]
        mock_kokoro.create.side_effect = RuntimeError("synthesis failed")

        with patch("jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro):
            tts = KokoroTTS()
            await tts.load()
            with pytest.raises(TTSError, match="synthesis failed"):
                await tts.synthesize("hello")

    @pytest.mark.asyncio
    async def test_list_voices(self) -> None:
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah", "bf_emma", "am_adam"]

        with patch("jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro):
            tts = KokoroTTS()
            await tts.load()
            voices = tts.list_voices()
            assert voices == ["af_sarah", "bf_emma", "am_adam"]

    def test_list_voices_without_load_raises(self) -> None:
        tts = KokoroTTS()
        with pytest.raises(TTSError, match="not loaded"):
            tts.list_voices()

    @pytest.mark.asyncio
    async def test_unload(self) -> None:
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah"]

        with patch("jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro):
            tts = KokoroTTS()
            await tts.load()
            assert tts.is_loaded

            await tts.unload()
            assert not tts.is_loaded

    @pytest.mark.asyncio
    async def test_synthesize_stream_without_load_raises(self) -> None:
        tts = KokoroTTS()
        with pytest.raises(TTSError, match="not loaded"):
            async for _ in tts.synthesize_stream("hello"):
                pass

    @pytest.mark.asyncio
    async def test_synthesize_stream_empty_text_raises(self) -> None:
        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah"]

        with patch("jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro):
            tts = KokoroTTS()
            await tts.load()
            with pytest.raises(TTSError, match="empty text"):
                async for _ in tts.synthesize_stream("  "):
                    pass

    @pytest.mark.asyncio
    async def test_synthesize_stream_yields_chunks(self) -> None:
        audio1 = np.zeros(1000, dtype=np.float32)
        audio2 = np.zeros(2000, dtype=np.float32)

        async def mock_create_stream(text: str, voice: str, speed: float, lang: str) -> None:
            """This won't be used directly — we mock the async generator."""

        mock_kokoro = MagicMock()
        mock_kokoro.get_voices.return_value = ["af_sarah"]

        # Create a proper async generator
        async def fake_stream(*args: object, **kwargs: object) -> None:
            yield (audio1, 24000)
            yield (audio2, 24000)

        mock_kokoro.create_stream = fake_stream

        with patch("jarvis.tts.kokoro_tts.KokoroTTS._load_sync", return_value=mock_kokoro):
            tts = KokoroTTS()
            await tts.load()

            chunks = []
            async for chunk in tts.synthesize_stream("hello world"):
                chunks.append(chunk)

            assert len(chunks) == 2
            assert isinstance(chunks[0], TTSResult)
            assert len(chunks[0].audio) == 1000
            assert len(chunks[1].audio) == 2000
