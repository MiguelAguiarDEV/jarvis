"""Tests for ChatGPT LLM provider."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.llm.base import LLMMessage, ToolCall
from jarvis.llm.chatgpt_provider import ChatGPTProvider
from jarvis.tools.base import ToolDefinition


class TestChatGPTProvider:
    def test_name(self) -> None:
        p = ChatGPTProvider(access_token="test-token")
        assert p.name == "chatgpt"

    def test_is_available_with_token(self) -> None:
        assert ChatGPTProvider(access_token="test-token").is_available

    def test_is_not_available_without_token(self) -> None:
        assert not ChatGPTProvider(access_token="").is_available

    def test_convert_messages_with_system_prompt(self) -> None:
        p = ChatGPTProvider(access_token="test")
        msgs = [LLMMessage(role="user", content="hello")]
        result = p._convert_messages(msgs, system_prompt="You are Jarvis")
        assert result[0] == {"role": "system", "content": "You are Jarvis"}
        assert result[1] == {"role": "user", "content": "hello"}

    def test_convert_messages_tool_calls(self) -> None:
        p = ChatGPTProvider(access_token="test")
        tc = ToolCall(id="tc_1", name="system_info", arguments={"fields": ["time"]})
        msgs = [LLMMessage(role="assistant", content="Checking", tool_calls=[tc])]
        result = p._convert_messages(msgs, system_prompt=None)
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "Checking"
        assert result[0]["tool_calls"][0]["id"] == "tc_1"
        assert result[0]["tool_calls"][0]["type"] == "function"
        # Arguments should be JSON string
        args = result[0]["tool_calls"][0]["function"]["arguments"]
        assert json.loads(args) == {"fields": ["time"]}

    def test_convert_messages_tool_result(self) -> None:
        p = ChatGPTProvider(access_token="test")
        msgs = [LLMMessage(role="tool", content='{"time":"12:00"}', tool_call_id="tc_1")]
        result = p._convert_messages(msgs, system_prompt=None)
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "tc_1"

    def test_convert_tools(self) -> None:
        p = ChatGPTProvider(access_token="test")
        tools = [
            ToolDefinition(
                name="system_info",
                description="Get system info",
                parameters={"type": "object", "properties": {}},
            )
        ]
        result = p._convert_tools(tools)
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "system_info"

    def test_parse_response_text(self) -> None:
        p = ChatGPTProvider(access_token="test")
        mock_msg = MagicMock()
        mock_msg.content = "Hello!"
        mock_msg.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_choice.finish_reason = "stop"

        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.model = "gpt-4o"
        mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

        result = p._parse_response(mock_resp)
        assert result.content == "Hello!"
        assert result.tool_calls == []
        assert result.finish_reason == "stop"

    def test_parse_response_tool_calls(self) -> None:
        p = ChatGPTProvider(access_token="test")
        mock_tc = MagicMock()
        mock_tc.id = "tc_1"
        mock_tc.function.name = "system_info"
        mock_tc.function.arguments = '{"fields": ["time"]}'

        mock_msg = MagicMock()
        mock_msg.content = None
        mock_msg.tool_calls = [mock_tc]

        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_choice.finish_reason = "tool_calls"

        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.model = "gpt-4o"
        mock_resp.usage = MagicMock(prompt_tokens=20, completion_tokens=10)

        result = p._parse_response(mock_resp)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].arguments == {"fields": ["time"]}
        assert result.finish_reason == "tool_use"

    def test_parse_response_invalid_json_arguments(self) -> None:
        p = ChatGPTProvider(access_token="test")
        mock_tc = MagicMock()
        mock_tc.id = "tc_1"
        mock_tc.function.name = "test"
        mock_tc.function.arguments = "not json"

        mock_msg = MagicMock()
        mock_msg.content = None
        mock_msg.tool_calls = [mock_tc]

        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_choice.finish_reason = "tool_calls"

        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.model = "gpt-4o"
        mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

        result = p._parse_response(mock_resp)
        assert result.tool_calls[0].arguments == {}

    @pytest.mark.asyncio
    async def test_check_health_success(self) -> None:
        p = ChatGPTProvider(access_token="test")
        p._client.chat.completions.create = AsyncMock(return_value=MagicMock())
        assert await p.check_health() is True

    @pytest.mark.asyncio
    async def test_check_health_failure(self) -> None:
        p = ChatGPTProvider(access_token="test")
        p._client.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
        assert await p.check_health() is False
