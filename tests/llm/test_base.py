"""Tests for LLM base types."""

from __future__ import annotations

import pytest

from jarvis.llm.base import LLMMessage, LLMResponse, ToolCall


class TestToolCall:
    def test_creation(self) -> None:
        tc = ToolCall(id="tc_1", name="system_info", arguments={"fields": ["time"]})
        assert tc.id == "tc_1"
        assert tc.name == "system_info"
        assert tc.arguments == {"fields": ["time"]}

    def test_frozen(self) -> None:
        tc = ToolCall(id="tc_1", name="test", arguments={})
        with pytest.raises(AttributeError):
            tc.name = "changed"  # type: ignore[misc]


class TestLLMMessage:
    def test_user_message(self) -> None:
        msg = LLMMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.tool_calls == []
        assert msg.tool_call_id is None

    def test_assistant_with_tool_calls(self) -> None:
        tc = ToolCall(id="tc_1", name="test", arguments={})
        msg = LLMMessage(role="assistant", content=None, tool_calls=[tc])
        assert len(msg.tool_calls) == 1

    def test_tool_result_message(self) -> None:
        msg = LLMMessage(role="tool", content='{"time": "12:00"}', tool_call_id="tc_1")
        assert msg.role == "tool"
        assert msg.tool_call_id == "tc_1"


class TestLLMResponse:
    def test_text_response(self) -> None:
        resp = LLMResponse(
            content="Hello!",
            tool_calls=[],
            provider="claude",
            model="claude-sonnet",
            usage={"input_tokens": 10, "output_tokens": 5},
            finish_reason="stop",
        )
        assert resp.content == "Hello!"
        assert resp.provider == "claude"
        assert resp.finish_reason == "stop"

    def test_tool_use_response(self) -> None:
        tc = ToolCall(id="tc_1", name="system_info", arguments={"fields": ["time"]})
        resp = LLMResponse(
            content=None,
            tool_calls=[tc],
            provider="chatgpt",
            model="gpt-4o",
            usage={"input_tokens": 20, "output_tokens": 10},
            finish_reason="tool_use",
        )
        assert len(resp.tool_calls) == 1
        assert resp.finish_reason == "tool_use"
