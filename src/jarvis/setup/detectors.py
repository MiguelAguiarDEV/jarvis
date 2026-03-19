"""System detection utilities for setup wizard.

Detects: Python, uv, CUDA/GPU, audio devices, Ollama.
All functions are async and safe to call on any platform.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """Result of a system detection check."""

    found: bool
    name: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class GPUInfo:
    """GPU detection result."""

    found: bool
    name: str = ""
    vram_mb: int = 0
    cuda_version: str = ""


@dataclass(frozen=True, slots=True)
class AudioDevice:
    """Detected audio device."""

    index: int
    name: str
    is_input: bool
    is_default: bool


async def detect_python() -> DetectionResult:
    """Detect Python version."""
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 12)
    return DetectionResult(
        found=ok,
        name="Python",
        detail=f"{version}" + ("" if ok else " (requires 3.12+)"),
    )


async def detect_uv() -> DetectionResult:
    """Detect if uv is installed."""
    uv_path = shutil.which("uv")
    if not uv_path:
        return DetectionResult(found=False, name="uv", detail="not found in PATH")

    try:
        proc = await asyncio.create_subprocess_exec(
            "uv",
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        version = stdout.decode().strip()
        return DetectionResult(found=True, name="uv", detail=version)
    except Exception as e:
        return DetectionResult(found=False, name="uv", detail=str(e))


async def detect_cuda() -> GPUInfo:
    """Detect NVIDIA GPU and CUDA via nvidia-smi."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return GPUInfo(found=False)

    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        output = stdout.decode().strip()

        if not output:
            return GPUInfo(found=False)

        # Parse first GPU: "NVIDIA GeForce RTX 4060, 8188, 560.35.03"
        parts = [p.strip() for p in output.split("\n")[0].split(",")]
        name = parts[0] if len(parts) > 0 else "Unknown GPU"
        vram_mb = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        driver = parts[2] if len(parts) > 2 else ""

        return GPUInfo(found=True, name=name, vram_mb=vram_mb, cuda_version=driver)
    except Exception:
        return GPUInfo(found=False)


async def detect_audio_devices() -> list[AudioDevice]:
    """Detect audio input/output devices via PyAudio.

    Returns empty list if PyAudio is not available.
    """
    try:
        import pyaudio
    except ImportError:
        return []

    devices: list[AudioDevice] = []
    try:
        pa = pyaudio.PyAudio()
        default_input = pa.get_default_input_device_info().get("index", -1)
        default_output = pa.get_default_output_device_info().get("index", -1)

        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            name = str(info.get("name", f"Device {i}"))
            max_input = int(info.get("maxInputChannels", 0))
            max_output = int(info.get("maxOutputChannels", 0))

            if max_input > 0:
                devices.append(
                    AudioDevice(
                        index=i,
                        name=name,
                        is_input=True,
                        is_default=(i == default_input),
                    )
                )
            if max_output > 0:
                devices.append(
                    AudioDevice(
                        index=i,
                        name=name,
                        is_input=False,
                        is_default=(i == default_output),
                    )
                )

        pa.terminate()
    except Exception:
        pass

    return devices


async def detect_ollama() -> tuple[bool, list[str]]:
    """Detect if Ollama is running and list available models.

    Returns:
        Tuple of (is_running, model_names).
    """
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code != 200:
                return False, []
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            return True, models
    except Exception:
        return False, []


async def detect_env_file() -> DetectionResult:
    """Check if .env file exists."""
    from pathlib import Path

    env_path = Path(".env")
    if env_path.exists():
        from jarvis.setup.env_writer import read_env

        config = read_env(env_path)
        return DetectionResult(
            found=True,
            name=".env",
            detail=f"{len(config)} keys configured",
        )
    return DetectionResult(found=False, name=".env", detail="not found")


async def detect_tts_models() -> DetectionResult:
    """Check if TTS model files exist."""
    from pathlib import Path

    model = Path("models/kokoro-v1.0.onnx")
    voices = Path("models/voices-v1.0.bin")

    if model.exists() and voices.exists():
        size_mb = (model.stat().st_size + voices.stat().st_size) / 1024 / 1024
        return DetectionResult(found=True, name="TTS Models", detail=f"{size_mb:.0f}MB")
    missing = []
    if not model.exists():
        missing.append("kokoro-v1.0.onnx")
    if not voices.exists():
        missing.append("voices-v1.0.bin")
    return DetectionResult(found=False, name="TTS Models", detail=f"missing: {', '.join(missing)}")


async def run_all_detections() -> dict[
    str, DetectionResult | GPUInfo | list[AudioDevice] | tuple[bool, list[str]]
]:
    """Run all detections in parallel.

    Returns:
        Dict with keys: python, uv, cuda, audio_devices, ollama, env_file, tts_models.
    """
    results = await asyncio.gather(
        detect_python(),
        detect_uv(),
        detect_cuda(),
        detect_audio_devices(),
        detect_ollama(),
        detect_env_file(),
        detect_tts_models(),
    )

    return {
        "python": results[0],
        "uv": results[1],
        "cuda": results[2],
        "audio_devices": results[3],
        "ollama": results[4],
        "env_file": results[5],
        "tts_models": results[6],
    }
