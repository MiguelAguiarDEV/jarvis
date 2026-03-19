"""Tests for LLM router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.llm.base import (
    AllProvidersFailedError,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
)
from jarvis.llm.router import LLMRouter
from jarvis.tools.base import ToolDefinition


def _make_provider(
    name: str,
    available: bool = True,
    response: LLMResponse | None = None,
    error: Exception | None = None,
) -> LLMProvider:
    """Create a mock LLM provider."""
    provider = MagicMock(spec=LLMProvider)
    provider.name = name
    provider.is_available = available

    if error:
        provider.complete = AsyncMock(side_effect=error)
    elif response:
        provider.complete = AsyncMock(return_value=response)
    else:
        provider.complete = AsyncMock(
            return_value=LLMResponse(
                content=f"Response from {name}",
                tool_calls=[],
                provider=name,
                model=f"{name}-model",
                usage={"input_tokens": 10, "output_tokens": 5},
                finish_reason="stop",
            )
        )

    provider.check_health = AsyncMock(return_value=available)
    return provider


class TestLLMRouter:
    """Test LLMRouter."""

    def test_providers_and_priority(self) -> None:
        p1 = _make_provider("claude")
        p2 = _make_provider("chatgpt")
        router = LLMRouter({"claude": p1, "chatgpt": p2}, priority=["claude", "chatgpt"])

        assert len(router.providers) == 2
        assert router.priority == ["claude", "chatgpt"]

    @pytest.mark.asyncio
    async def test_routes_to_first_available(self) -> None:
        p1 = _make_provider("claude")
        p2 = _make_provider("chatgpt")
        router = LLMRouter({"claude": p1, "chatgpt": p2}, priority=["claude", "chatgpt"])

        messages = [LLMMessage(role="user", content="hello")]
        result = await router.complete(messages)

        assert result.provider == "claude"
        p1.complete.assert_called_once()
        p2.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_on_error(self) -> None:
        p1 = _make_provider("claude", error=LLMProviderError("auth failed"))
        p2 = _make_provider("chatgpt")
        router = LLMRouter({"claude": p1, "chatgpt": p2}, priority=["claude", "chatgpt"])

        messages = [LLMMessage(role="user", content="hello")]
        result = await router.complete(messages)

        assert result.provider == "chatgpt"

    @pytest.mark.asyncio
    async def test_skips_unavailable(self) -> None:
        p1 = _make_provider("claude", available=False)
        p2 = _make_provider("chatgpt")
        router = LLMRouter({"claude": p1, "chatgpt": p2}, priority=["claude", "chatgpt"])

        messages = [LLMMessage(role="user", content="hello")]
        result = await router.complete(messages)

        assert result.provider == "chatgpt"
        p1.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_fail_raises(self) -> None:
        p1 = _make_provider("claude", error=LLMProviderError("fail 1"))
        p2 = _make_provider("chatgpt", error=LLMProviderError("fail 2"))
        router = LLMRouter({"claude": p1, "chatgpt": p2}, priority=["claude", "chatgpt"])

        messages = [LLMMessage(role="user", content="hello")]
        with pytest.raises(AllProvidersFailedError, match="All LLM providers failed"):
            await router.complete(messages)

    @pytest.mark.asyncio
    async def test_preferred_provider_override(self) -> None:
        p1 = _make_provider("claude")
        p2 = _make_provider("chatgpt")
        router = LLMRouter({"claude": p1, "chatgpt": p2}, priority=["claude", "chatgpt"])

        messages = [LLMMessage(role="user", content="hello")]
        result = await router.complete(messages, preferred_provider="chatgpt")

        assert result.provider == "chatgpt"

    @pytest.mark.asyncio
    async def test_preferred_falls_back_to_priority(self) -> None:
        p1 = _make_provider("claude")
        p2 = _make_provider("chatgpt", error=LLMProviderError("fail"))
        router = LLMRouter({"claude": p1, "chatgpt": p2}, priority=["claude", "chatgpt"])

        messages = [LLMMessage(role="user", content="hello")]
        result = await router.complete(messages, preferred_provider="chatgpt")

        # chatgpt fails, falls back to claude
        assert result.provider == "claude"

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        p1 = _make_provider("claude", available=True)
        p2 = _make_provider("chatgpt", available=False)
        router = LLMRouter({"claude": p1, "chatgpt": p2})

        health = await router.health_check()
        assert health["claude"] is True
        assert health["chatgpt"] is False

    def test_get_provider(self) -> None:
        p1 = _make_provider("claude")
        router = LLMRouter({"claude": p1})

        assert router.get_provider("claude") is p1
        assert router.get_provider("nonexistent") is None

    @pytest.mark.asyncio
    async def test_passes_tools_and_system_prompt(self) -> None:
        p1 = _make_provider("claude")
        router = LLMRouter({"claude": p1}, priority=["claude"])

        tools = [ToolDefinition(name="test", description="test tool", parameters={})]
        messages = [LLMMessage(role="user", content="hello")]
        await router.complete(messages, tools=tools, system_prompt="You are Jarvis.")

        call_kwargs = p1.complete.call_args[1]
        assert call_kwargs["tools"] == tools
        assert call_kwargs["system_prompt"] == "You are Jarvis."
