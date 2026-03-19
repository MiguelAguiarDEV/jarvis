"""Entry point for `python -m jarvis`."""

import asyncio
import contextlib
import signal
import sys

import structlog

from jarvis import __version__
from jarvis.config import JarvisSettings
from jarvis.logging import configure_logging
from jarvis.pipeline.main_loop import JarvisPipeline

log = structlog.get_logger()


async def main() -> None:
    """Initialize and run JARVIS."""
    settings = JarvisSettings()
    configure_logging(level=settings.log_level)

    log.info(
        "jarvis.starting",
        version=__version__,
        llm_preferred=settings.llm_preferred,
        stt_device=settings.stt_device,
        tts_voice=settings.tts_voice,
        wake_word=settings.wake_word,
    )

    pipeline = JarvisPipeline(settings)

    # Register signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    _shutdown_task: asyncio.Task[None] | None = None

    def _signal_handler() -> None:
        nonlocal _shutdown_task
        log.info("jarvis.shutdown_requested")
        _shutdown_task = asyncio.ensure_future(pipeline.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _signal_handler)

    try:
        await pipeline.initialize()
        log.info("jarvis.ready", message="Say the wake word to begin.")
        await pipeline.run()
    except KeyboardInterrupt:
        pass
    except Exception:
        log.exception("jarvis.fatal_error")
        sys.exit(1)
    finally:
        await pipeline.shutdown()
        log.info("jarvis.stopped")


def run() -> None:
    """Sync wrapper for main."""
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
    sys.exit(0)


if __name__ == "__main__":
    run()
