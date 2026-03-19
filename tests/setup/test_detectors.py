"""Tests for system detectors."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from jarvis.setup.detectors import (
    AudioDevice,
    DetectionResult,
    GPUInfo,
    detect_cuda,
    detect_ollama,
    detect_python,
    detect_uv,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestDetectionResult:
    def test_creation(self) -> None:
        r = DetectionResult(found=True, name="Python", detail="3.12.3")
        assert r.found
        assert r.name == "Python"
        assert r.detail == "3.12.3"


class TestGPUInfo:
    def test_not_found(self) -> None:
        g = GPUInfo(found=False)
        assert not g.found
        assert g.name == ""
        assert g.vram_mb == 0


class TestDetectPython:
    @pytest.mark.asyncio
    async def test_detects_current_python(self) -> None:
        result = await detect_python()
        assert result.name == "Python"
        assert str(sys.version_info.major) in result.detail


class TestDetectUv:
    @pytest.mark.asyncio
    async def test_detects_uv_when_installed(self) -> None:
        result = await detect_uv()
        # uv is installed in our dev environment
        assert result.name == "uv"
        assert result.found

    @pytest.mark.asyncio
    async def test_not_found_when_missing(self) -> None:
        with patch("jarvis.setup.detectors.shutil.which", return_value=None):
            result = await detect_uv()
            assert not result.found


class TestDetectCuda:
    @pytest.mark.asyncio
    async def test_not_found_without_nvidia_smi(self) -> None:
        with patch("jarvis.setup.detectors.shutil.which", return_value=None):
            result = await detect_cuda()
            assert not result.found

    @pytest.mark.asyncio
    async def test_parses_nvidia_smi_output(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"NVIDIA GeForce RTX 4060, 8188, 560.35\n", b"")
        )

        with (
            patch("jarvis.setup.detectors.shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            result = await detect_cuda()
            assert result.found
            assert "RTX 4060" in result.name
            assert result.vram_mb == 8188


class TestDetectOllama:
    @pytest.mark.asyncio
    async def test_not_running(self) -> None:
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            running, models = await detect_ollama()
            assert not running
            assert models == []


class TestDetectEnvFile:
    @pytest.mark.asyncio
    async def test_not_found(self, tmp_path: Path) -> None:
        with patch("jarvis.setup.detectors.detect_env_file") as mock_detect:
            mock_detect.return_value = DetectionResult(found=False, name=".env", detail="not found")
            result = await mock_detect()
            assert not result.found


class TestDetectTtsModels:
    @pytest.mark.asyncio
    async def test_not_found(self, tmp_path: Path) -> None:
        with patch("jarvis.setup.detectors.detect_tts_models") as mock_detect:
            mock_detect.return_value = DetectionResult(
                found=False, name="TTS Models", detail="missing: kokoro-v1.0.onnx, voices-v1.0.bin"
            )
            result = await mock_detect()
            assert not result.found


class TestAudioDevice:
    def test_creation(self) -> None:
        d = AudioDevice(index=0, name="USB Mic", is_input=True, is_default=True)
        assert d.name == "USB Mic"
        assert d.is_input
        assert d.is_default
