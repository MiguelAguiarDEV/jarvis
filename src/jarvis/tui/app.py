"""JARVIS Dashboard — main Textual application."""

from __future__ import annotations

import structlog
from textual.app import App

from jarvis import __version__
from jarvis.config import JarvisSettings
from jarvis.logging import configure_logging
from jarvis.pipeline.main_loop import JarvisPipeline
from jarvis.tui.events import PipelineEventBridge
from jarvis.tui.log_buffer import TUILogBuffer
from jarvis.tui.screens.dashboard import DashboardScreen

log = structlog.get_logger()


class JarvisDashboard(App[None]):
    """Main JARVIS TUI application.

    Runs the voice pipeline as a background worker while
    displaying real-time status in the dashboard.
    """

    TITLE = f"JARVIS v{__version__}"
    CSS_PATH = None  # Screens provide their own CSS

    def __init__(self) -> None:
        super().__init__()
        self._settings = JarvisSettings()
        self._log_buffer = TUILogBuffer(maxlen=1000)
        self._bridge = PipelineEventBridge(self)
        self._pipeline = JarvisPipeline(
            self._settings,
            event_callback=self._bridge.dispatch,
        )

    def on_mount(self) -> None:
        """Start pipeline in background when app mounts."""
        configure_logging(level=self._settings.log_level)
        log.info("jarvis.dashboard.starting", version=__version__)

        self.push_screen(DashboardScreen())
        self.run_worker(self._start_pipeline(), name="pipeline", exclusive=True)

    async def _start_pipeline(self) -> None:
        """Initialize and run pipeline as background worker."""
        try:
            await self._pipeline.initialize()
            await self._pipeline.run()
        except Exception:
            log.exception("jarvis.dashboard.pipeline_error")
            self._bridge.dispatch("error", error="Pipeline crashed", stage="pipeline")

    async def action_quit(self) -> None:
        """Graceful shutdown."""
        log.info("jarvis.dashboard.shutting_down")
        await self._pipeline.shutdown()
        self.exit()


def run_dashboard() -> None:
    """Entry point for dashboard mode."""
    app = JarvisDashboard()
    app.run()
