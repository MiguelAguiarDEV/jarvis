"""Tests for Claude LLM provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.llm.base import LLMMessage, LLMProviderError, ToolCall
from jarvis.llm.claude_provider import ClaudeProvider
from jarvis.tools.base import ToolDefinition


class TestClaudeProvider:
    def test_name(self) -> None:
        p = ClaudeProvider(api_key="test-key")
        assert p.name == "claude"

    def test_is_available_with_key(self) -> None:
        assert ClaudeProvider(api_key="test-key").is_available

    def test_is_not_available_without_key(self) -> None:
        assert not ClaudeProvider(api_key="").is_available

    def test_convert_messages_user(self) -> None:
        p = ClaudeProvider(api_key="test")
        msgs = [LLMMessage(role="user", content="hello")]
        result = p._convert_messages(msgs)
        assert result == [{"role": "user", "content": "hello"}]

    def test_convert_messages_skips_system(self) -> None:
        p = ClaudeProvider(api_key="test")
        msgs = [
            LLMMessage(role="system", content="you are jarvis"),
            LLMMessage(role="user", content="hello"),
        ]
        result = p._convert_messages(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_convert_messages_tool_calls(self) -> None:
        p = ClaudeProvider(api_key="test")
        tc = ToolCall(id="tc_1", name="system_info", arguments={"fields": ["time"]})
        msgs = [LLMMessage(role="assistant", content="Let me check", tool_calls=[tc])]
        result = p._convert_messages(msgs)
        assert result[0]["role"] == "assistant"
        content = result[0]["content"]
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "tool_use"
        assert content[1]["id"] == "tc_1"

    def test_convert_messages_tool_result(self) -> None:
        p = ClaudeProvider(api_key="test")
        msgs = [LLMMessage(role="tool", content='{"time":"12:00"}', tool_call_id="tc_1")]
        result = p._convert_messages(msgs)
        assert result[0]["role"] == "user"
        assert result[0]["content"][0]["type"] == "tool_result"
        assert result[0]["content"][0]["tool_use_id"] == "tc_1"

    def test_convert_tools(self) -> None:
        p = ClaudeProvider(api_key="test")
        tools = [
            ToolDefinition(
                name="system_info",
                description="Get system info",
                parameters={"type": "object", "properties": {}},
            )
        ]
        result = p._convert_tools(tools)
        assert len(result) == 1
        assert result[0]["name"] == "system_info"
        assert "input_schema" in result[0]

    def test_parse_response_text(self) -> None:
        p = ClaudeProvider(api_key="test")
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(type="text", text="Hello!")]
        mock_resp.stop_reason = "end_turn"
        mock_resp.model = "claude-sonnet"
        mock_resp.usage = MagicMock(input_tokens=10, output_tokens=5)

        result = p._parse_response(mock_resp)
        assert result.content == "Hello!"
        assert result.tool_calls == []
        assert result.finish_reason == "stop"
        assert result.provider == "claude"

    def test_parse_response_tool_use(self) -> None:
        p = ClaudeProvider(api_key="test")
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.id = "tc_1"
        mock_block.name = "system_info"
        mock_block.input = {"fields": ["time"]}

        mock_resp = MagicMock()
        mock_resp.content = [mock_block]
        mock_resp.stop_reason = "tool_use"
        mock_resp.model = "claude-sonnet"
        mock_resp.usage = MagicMock(input_tokens=20, output_tokens=10)

        result = p._parse_response(mock_resp)
        assert result.content is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "system_info"
        assert result.finish_reason == "tool_use"

    @pytest.mark.asyncio
    async def test_complete_auth_error(self) -> None:
        import anthropic

        p = ClaudeProvider(api_key="bad-key")
        p._client.messages.create = AsyncMock(
            side_effect=anthropic.AuthenticationError(
                message="invalid key",
                response=MagicMock(status_code=401),
                body=None,
            )
        )

        msgs = [LLMMessage(role="user", content="hello")]
        with pytest.raises(LLMProviderError, match="authentication failed"):
            await p.complete(msgs)

    @pytest.mark.asyncio
    async def test_check_health_success(self) -> None:
        p = ClaudeProvider(api_key="test")
        p._client.messages.create = AsyncMock(return_value=MagicMock())
        assert await p.check_health() is True

    @pytest.mark.asyncio
    async def test_check_health_failure(self) -> None:
        p = ClaudeProvider(api_key="test")
        p._client.messages.create = AsyncMock(side_effect=Exception("fail"))
        assert await p.check_health() is False
