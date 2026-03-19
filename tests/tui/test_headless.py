"""Tests for headless mode."""

from __future__ import annotations

from jarvis.tui.headless import run_headless


class TestHeadless:
    def test_run_headless_is_callable(self) -> None:
        """run_headless exists and is callable."""
        assert callable(run_headless)
