"""Entry point for `python -m jarvis`."""

import asyncio
import contextlib
import signal
import sys

import structlog

from jarvis.config import JarvisSettings

log = structlog.get_logger()


async def main() -> None:
    """Initialize and run JARVIS."""
    settings = JarvisSettings()

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog, settings.log_level.upper(), structlog.INFO)  # type: ignore[arg-type]
        ),
    )

    log.info("jarvis.starting", version="0.1.0", llm_preferred=settings.llm_preferred)

    # Phase 1: placeholder — will be replaced by JarvisPipeline in Milestone 5
    log.info("jarvis.ready", message="JARVIS is ready. Pipeline not yet implemented.")

    # Keep alive until interrupted
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        log.info("jarvis.shutdown_requested")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            # Windows doesn't support add_signal_handler for SIGTERM
            loop.add_signal_handler(sig, _signal_handler)

    with contextlib.suppress(KeyboardInterrupt):
        await stop_event.wait()

    log.info("jarvis.stopped")


def run() -> None:
    """Sync wrapper for main."""
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
    sys.exit(0)


if __name__ == "__main__":
    run()
