"""Entry point for `python -m jarvis`.

Modes:
    jarvis              Launch TUI dashboard (default)
    jarvis setup        Launch setup wizard
    jarvis --headless   Voice-only mode (no TUI)
"""

from __future__ import annotations

import sys


def main() -> None:
    """Route to the appropriate mode based on CLI arguments."""
    args = sys.argv[1:]

    if "setup" in args:
        # Setup wizard TUI
        from jarvis.setup.app import run_setup

        run_setup()

    elif "--headless" in args:
        # Voice-only mode (original behavior)
        from jarvis.tui.headless import run_headless

        run_headless()

    else:
        # Default: TUI dashboard
        from jarvis.tui.app import run_dashboard

        run_dashboard()


if __name__ == "__main__":
    main()
