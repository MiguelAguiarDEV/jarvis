"""Headless mode — voice pipeline without TUI.

Equivalent to the original `python -m jarvis` behavior.
Used for running as a service/daemon or when no terminal is available.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
import sys

import structlog

from jarvis.config import JarvisSettings
from jarvis.logging import configure_logging
from jarvis.pipeline.main_loop import JarvisPipeline

log = structlog.get_logger()


async def _run_headless() -> None:
    """Initialize and run JARVIS in headless mode."""
    settings = JarvisSettings()
    configure_logging(level=settings.log_level)

    log.info(
        "jarvis.headless.starting",
        llm_preferred=settings.llm_preferred,
        stt_device=settings.stt_device,
    )

    pipeline = JarvisPipeline(settings)

    # Register signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    _shutdown_task: asyncio.Task[None] | None = None

    def _signal_handler() -> None:
        nonlocal _shutdown_task
        log.info("jarvis.headless.shutdown_requested")
        _shutdown_task = asyncio.ensure_future(pipeline.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _signal_handler)

    try:
        await pipeline.initialize()
        log.info("jarvis.headless.ready")
        await pipeline.run()
    except KeyboardInterrupt:
        pass
    except Exception:
        log.exception("jarvis.headless.fatal_error")
        sys.exit(1)
    finally:
        await pipeline.shutdown()
        log.info("jarvis.headless.stopped")


def run_headless() -> None:
    """Entry point for headless mode."""
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_run_headless())
