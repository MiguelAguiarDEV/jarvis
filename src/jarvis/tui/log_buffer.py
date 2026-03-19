"""Ring buffer for structured log entries, consumed by TUI log viewer.

Plugs into structlog as a processor. Captures fully-processed, redacted
log entries into a bounded deque that the LogsScreen reads from.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class LogEntry:
    """A single structured log entry."""

    timestamp: float
    level: str
    event: str
    fields: dict[str, Any] = field(default_factory=dict)

    @property
    def time_str(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.timestamp))


class TUILogBuffer:
    """Thread-safe ring buffer that captures structlog entries.

    Usage:
        buffer = TUILogBuffer(maxlen=1000)
        # Add buffer.processor to structlog chain
        # Read entries from buffer.entries
    """

    def __init__(self, maxlen: int = 1000) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=maxlen)

    @property
    def entries(self) -> list[LogEntry]:
        """All entries, oldest first."""
        return list(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def processor(
        self,
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Structlog processor — captures entry then passes through.

        Must be placed BEFORE the renderer in the processor chain
        so it receives the dict, not the final string.
        """
        entry = LogEntry(
            timestamp=time.time(),
            level=event_dict.get("level", method_name),
            event=str(event_dict.get("event", "")),
            fields={
                k: v for k, v in event_dict.items() if k not in ("event", "level", "timestamp")
            },
        )
        self._entries.append(entry)
        return event_dict

    def get_filtered(
        self,
        level: str | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        """Get filtered entries.

        Args:
            level: Minimum log level (debug, info, warning, error).
            search: Text search in event name and fields.
            limit: Max entries to return.

        Returns:
            Filtered entries, newest first.
        """
        level_order = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}
        min_level = level_order.get(level.lower(), 0) if level else 0

        results: list[LogEntry] = []
        for entry in reversed(self._entries):
            entry_level = level_order.get(entry.level.lower(), 0)
            if entry_level < min_level:
                continue

            if search:
                search_lower = search.lower()
                haystack = f"{entry.event} {entry.fields}".lower()
                if search_lower not in haystack:
                    continue

            results.append(entry)
            if len(results) >= limit:
                break

        return results
