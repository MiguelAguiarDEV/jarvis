"""Tests for TUI log buffer."""

from __future__ import annotations

from jarvis.tui.log_buffer import LogEntry, TUILogBuffer


class TestLogEntry:
    def test_creation(self) -> None:
        entry = LogEntry(timestamp=1234567890.0, level="info", event="test.event")
        assert entry.level == "info"
        assert entry.event == "test.event"

    def test_time_str(self) -> None:
        entry = LogEntry(timestamp=1234567890.0, level="info", event="test")
        assert ":" in entry.time_str  # HH:MM:SS format

    def test_fields_default_empty(self) -> None:
        entry = LogEntry(timestamp=0.0, level="info", event="test")
        assert entry.fields == {}


class TestTUILogBuffer:
    def test_empty_initially(self) -> None:
        buf = TUILogBuffer()
        assert buf.count == 0
        assert buf.entries == []

    def test_processor_captures_entry(self) -> None:
        buf = TUILogBuffer()
        event_dict = {"event": "test.event", "level": "info", "key": "value"}
        result = buf.processor(None, "info", event_dict)

        assert result is event_dict  # Passes through
        assert buf.count == 1
        assert buf.entries[0].event == "test.event"
        assert buf.entries[0].fields == {"key": "value"}

    def test_maxlen_enforced(self) -> None:
        buf = TUILogBuffer(maxlen=3)
        for i in range(5):
            buf.processor(None, "info", {"event": f"event_{i}", "level": "info"})

        assert buf.count == 3
        assert buf.entries[0].event == "event_2"
        assert buf.entries[2].event == "event_4"

    def test_clear(self) -> None:
        buf = TUILogBuffer()
        buf.processor(None, "info", {"event": "test", "level": "info"})
        assert buf.count == 1
        buf.clear()
        assert buf.count == 0

    def test_get_filtered_by_level(self) -> None:
        buf = TUILogBuffer()
        buf.processor(None, "debug", {"event": "debug_msg", "level": "debug"})
        buf.processor(None, "info", {"event": "info_msg", "level": "info"})
        buf.processor(None, "error", {"event": "error_msg", "level": "error"})

        errors = buf.get_filtered(level="error")
        assert len(errors) == 1
        assert errors[0].event == "error_msg"

        info_plus = buf.get_filtered(level="info")
        assert len(info_plus) == 2  # info + error

    def test_get_filtered_by_search(self) -> None:
        buf = TUILogBuffer()
        buf.processor(None, "info", {"event": "pipeline.started", "level": "info"})
        buf.processor(None, "info", {"event": "stt.loaded", "level": "info"})
        buf.processor(None, "info", {"event": "pipeline.stopped", "level": "info"})

        results = buf.get_filtered(search="pipeline")
        assert len(results) == 2

    def test_get_filtered_limit(self) -> None:
        buf = TUILogBuffer()
        for i in range(10):
            buf.processor(None, "info", {"event": f"event_{i}", "level": "info"})

        results = buf.get_filtered(limit=3)
        assert len(results) == 3
        # Newest first
        assert results[0].event == "event_9"

    def test_get_filtered_combined(self) -> None:
        buf = TUILogBuffer()
        buf.processor(None, "debug", {"event": "pipeline.debug", "level": "debug"})
        buf.processor(None, "info", {"event": "pipeline.info", "level": "info"})
        buf.processor(None, "error", {"event": "stt.error", "level": "error"})

        results = buf.get_filtered(level="info", search="pipeline")
        assert len(results) == 1
        assert results[0].event == "pipeline.info"
