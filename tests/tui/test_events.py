"""Tests for TUI event bridge."""

from __future__ import annotations

from unittest.mock import MagicMock

from jarvis.tui.events import (
    ConversationRecord,
    PipelineEventBridge,
    PipelineReadyMessage,
    StateChangedMessage,
)


class TestPipelineEventBridge:
    def test_dispatch_state_change(self) -> None:
        mock_app = MagicMock()
        bridge = PipelineEventBridge(mock_app)

        bridge.dispatch("state_change", old="idle", new="listening", request_id="abc123")

        mock_app.post_message.assert_called_once()
        msg = mock_app.post_message.call_args[0][0]
        assert isinstance(msg, StateChangedMessage)
        assert msg.old_state == "idle"
        assert msg.new_state == "listening"
        assert msg.request_id == "abc123"

    def test_dispatch_conversation_complete(self) -> None:
        mock_app = MagicMock()
        bridge = PipelineEventBridge(mock_app)

        bridge.dispatch(
            "conversation_complete",
            user_text="What time is it?",
            response_text="It's 2pm.",
            provider="claude",
            model="claude-sonnet",
            elapsed_ms=1500.0,
            tool_names=["system_info"],
            request_id="req_1",
        )

        mock_app.post_message.assert_called_once()
        assert len(bridge.conversations) == 1
        record = bridge.conversations[0]
        assert record.user_text == "What time is it?"
        assert record.provider == "claude"
        assert record.tool_names == ["system_info"]

    def test_dispatch_error(self) -> None:
        mock_app = MagicMock()
        bridge = PipelineEventBridge(mock_app)

        bridge.dispatch("error", error="Connection failed", stage="llm")

        mock_app.post_message.assert_called_once()

    def test_dispatch_ready(self) -> None:
        mock_app = MagicMock()
        bridge = PipelineEventBridge(mock_app)

        bridge.dispatch("ready", provider_health={"claude": True}, tool_count=1)

        mock_app.post_message.assert_called_once()
        msg = mock_app.post_message.call_args[0][0]
        assert isinstance(msg, PipelineReadyMessage)
        assert msg.provider_health == {"claude": True}
        assert msg.tool_count == 1

    def test_dispatch_unknown_event_is_noop(self) -> None:
        mock_app = MagicMock()
        bridge = PipelineEventBridge(mock_app)

        bridge.dispatch("unknown_event", foo="bar")

        mock_app.post_message.assert_not_called()

    def test_conversation_history_limit(self) -> None:
        mock_app = MagicMock()
        bridge = PipelineEventBridge(mock_app)
        bridge._max_history = 3

        for i in range(5):
            bridge.dispatch(
                "conversation_complete",
                user_text=f"msg {i}",
                response_text=f"resp {i}",
                provider="qwen",
                elapsed_ms=100.0,
            )

        assert len(bridge._conversations) == 3
        # Newest first in .conversations property
        assert bridge.conversations[0].user_text == "msg 4"

    def test_conversations_newest_first(self) -> None:
        mock_app = MagicMock()
        bridge = PipelineEventBridge(mock_app)

        bridge.dispatch(
            "conversation_complete",
            user_text="first",
            response_text="r1",
            provider="qwen",
            elapsed_ms=100.0,
        )
        bridge.dispatch(
            "conversation_complete",
            user_text="second",
            response_text="r2",
            provider="qwen",
            elapsed_ms=200.0,
        )

        convos = bridge.conversations
        assert convos[0].user_text == "second"
        assert convos[1].user_text == "first"


class TestConversationRecord:
    def test_creation(self) -> None:
        record = ConversationRecord(
            timestamp=1234567890.0,
            user_text="hello",
            response_text="hi",
            provider="claude",
            elapsed_ms=500.0,
            tool_names=["system_info"],
            request_id="req_1",
        )
        assert record.user_text == "hello"
        assert record.provider == "claude"
        assert record.tool_names == ["system_info"]
