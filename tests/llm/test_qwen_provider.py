"""Tests for Qwen/Ollama LLM provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.llm.base import LLMMessage, LLMProviderError, ToolCall
from jarvis.llm.qwen_provider import QwenProvider
from jarvis.tools.base import ToolDefinition


class TestQwenProvider:
    def test_name(self) -> None:
        p = QwenProvider()
        assert p.name == "qwen"

    def test_is_always_available(self) -> None:
        assert QwenProvider().is_available

    def test_convert_messages_with_system_prompt(self) -> None:
        p = QwenProvider()
        msgs = [LLMMessage(role="user", content="hello")]
        result = p._convert_messages(msgs, system_prompt="You are Jarvis")
        assert result[0] == {"role": "system", "content": "You are Jarvis"}
        assert result[1] == {"role": "user", "content": "hello"}

    def test_convert_messages_tool_calls(self) -> None:
        p = QwenProvider()
        tc = ToolCall(id="tc_1", name="system_info", arguments={"fields": ["time"]})
        msgs = [LLMMessage(role="assistant", content="", tool_calls=[tc])]
        result = p._convert_messages(msgs, system_prompt=None)
        assert result[0]["tool_calls"][0]["function"]["name"] == "system_info"
        assert result[0]["tool_calls"][0]["function"]["arguments"] == {"fields": ["time"]}

    def test_convert_messages_tool_result(self) -> None:
        p = QwenProvider()
        msgs = [LLMMessage(role="tool", content='{"time":"12:00"}')]
        result = p._convert_messages(msgs, system_prompt=None)
        assert result[0]["role"] == "tool"

    def test_convert_tools(self) -> None:
        p = QwenProvider()
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
        p = QwenProvider()
        data = {
            "model": "qwen3.5:9b",
            "message": {"content": "Hello!", "role": "assistant"},
            "eval_count": 5,
            "prompt_eval_count": 10,
        }
        result = p._parse_response(data)
        assert result.content == "Hello!"
        assert result.tool_calls == []
        assert result.finish_reason == "stop"
        assert result.provider == "qwen"

    def test_parse_response_tool_calls(self) -> None:
        p = QwenProvider()
        data = {
            "model": "qwen3.5:9b",
            "message": {
                "content": "",
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "system_info",
                            "arguments": {"fields": ["time"]},
                        }
                    }
                ],
            },
            "eval_count": 10,
            "prompt_eval_count": 20,
        }
        result = p._parse_response(data)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "system_info"
        assert result.tool_calls[0].arguments == {"fields": ["time"]}
        assert result.finish_reason == "tool_use"

    def test_parse_response_tool_calls_string_arguments(self) -> None:
        """Ollama may return arguments as JSON string."""
        p = QwenProvider()
        data = {
            "model": "qwen3.5:9b",
            "message": {
                "content": "",
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "system_info",
                            "arguments": '{"fields": ["time"]}',
                        }
                    }
                ],
            },
        }
        result = p._parse_response(data)
        assert result.tool_calls[0].arguments == {"fields": ["time"]}

    def test_parse_response_empty_content_is_none(self) -> None:
        p = QwenProvider()
        data = {
            "model": "qwen3.5:9b",
            "message": {"content": "", "role": "assistant"},
        }
        result = p._parse_response(data)
        assert result.content is None

    @pytest.mark.asyncio
    async def test_check_health_success(self) -> None:
        p = QwenProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "qwen3.5:9b"}]}
        p._client.get = AsyncMock(return_value=mock_response)
        assert await p.check_health() is True

    @pytest.mark.asyncio
    async def test_check_health_model_not_found(self) -> None:
        p = QwenProvider(model="qwen3.5:9b")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3:8b"}]}
        p._client.get = AsyncMock(return_value=mock_response)
        assert await p.check_health() is False

    @pytest.mark.asyncio
    async def test_check_health_connection_error(self) -> None:
        import httpx

        p = QwenProvider()
        p._client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        assert await p.check_health() is False

    @pytest.mark.asyncio
    async def test_complete_connection_error(self) -> None:
        import httpx

        p = QwenProvider()
        p._client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        msgs = [LLMMessage(role="user", content="hello")]
        with pytest.raises(LLMProviderError, match="Cannot connect"):
            await p.complete(msgs)

    @pytest.mark.asyncio
    async def test_complete_timeout(self) -> None:
        import httpx

        p = QwenProvider()
        p._client.post = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))

        msgs = [LLMMessage(role="user", content="hello")]
        with pytest.raises(LLMProviderError, match="timed out"):
            await p.complete(msgs)

    @pytest.mark.asyncio
    async def test_complete_bad_status(self) -> None:
        p = QwenProvider()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "internal error"
        p._client.post = AsyncMock(return_value=mock_response)

        msgs = [LLMMessage(role="user", content="hello")]
        with pytest.raises(LLMProviderError, match="status 500"):
            await p.complete(msgs)
