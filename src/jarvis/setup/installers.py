"""Model download and dependency installation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    """Progress update during a file download."""

    filename: str
    downloaded_bytes: int
    total_bytes: int

    @property
    def percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, (self.downloaded_bytes / self.total_bytes) * 100)

    @property
    def downloaded_mb(self) -> float:
        return self.downloaded_bytes / 1024 / 1024

    @property
    def total_mb(self) -> float:
        return self.total_bytes / 1024 / 1024


TTS_MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/kokoro-v1.0.onnx"
)
TTS_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
)


async def download_file(
    url: str,
    dest: Path,
    filename: str | None = None,
) -> AsyncGenerator[DownloadProgress, None]:
    """Download a file with streaming progress updates.

    Args:
        url: URL to download from.
        dest: Destination file path.
        filename: Display name for progress (defaults to dest.name).

    Yields:
        DownloadProgress updates as data arrives.
    """
    name = filename or dest.name
    dest.parent.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(follow_redirects=True, timeout=300.0) as client:  # noqa: SIM117
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with dest.open("wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    yield DownloadProgress(
                        filename=name,
                        downloaded_bytes=downloaded,
                        total_bytes=total,
                    )


async def download_tts_models(
    models_dir: Path = Path("models"),
) -> AsyncGenerator[DownloadProgress, None]:
    """Download Kokoro TTS model files.

    Yields progress for both files sequentially.
    Skips files that already exist.
    """
    model_path = models_dir / "kokoro-v1.0.onnx"
    voices_path = models_dir / "voices-v1.0.bin"

    if not model_path.exists():
        async for progress in download_file(TTS_MODEL_URL, model_path, "kokoro-v1.0.onnx"):
            yield progress

    if not voices_path.exists():
        async for progress in download_file(TTS_VOICES_URL, voices_path, "voices-v1.0.bin"):
            yield progress
