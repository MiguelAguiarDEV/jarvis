"""Anthropic Claude LLM provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import anthropic
import structlog

from jarvis.llm.base import LLMMessage, LLMProvider, LLMProviderError, LLMResponse, ToolCall

if TYPE_CHECKING:
    from jarvis.tools.base import ToolDefinition

log = structlog.get_logger()


class ClaudeProvider(LLMProvider):
    """Anthropic Claude via official SDK.

    Auth: setup-token from config. The token is loaded at init,
    never passed to the LLM itself.
    """

    MODEL: str = "claude-sonnet-4-20250514"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        self._api_key = api_key
        self._model = model or self.MODEL
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def name(self) -> str:
        return "claude"

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    async def check_health(self) -> bool:
        """Send a minimal request to verify API key validity."""
        try:
            await self._client.messages.create(
                model=self._model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except Exception:
            return False

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send messages to Claude and get a completion."""
        try:
            api_messages = self._convert_messages(messages)
            kwargs: dict[str, Any] = {
                "model": self._model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": api_messages,
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            if tools:
                kwargs["tools"] = self._convert_tools(tools)

            response = await self._client.messages.create(**kwargs)
            return self._parse_response(response)

        except anthropic.AuthenticationError as e:
            msg = f"Claude authentication failed: {e}"
            raise LLMProviderError(msg) from e
        except anthropic.RateLimitError as e:
            msg = f"Claude rate limit exceeded: {e}"
            raise LLMProviderError(msg) from e
        except anthropic.APIError as e:
            msg = f"Claude API error: {e}"
            raise LLMProviderError(msg) from e
        except LLMProviderError:
            raise
        except Exception as e:
            msg = f"Claude unexpected error: {e}"
            raise LLMProviderError(msg) from e

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert internal messages to Anthropic API format."""
        api_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                # System messages handled separately in Anthropic API
                continue

            if msg.role == "assistant" and msg.tool_calls:
                # Assistant message with tool calls
                content: list[dict[str, Any]] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                api_messages.append({"role": "assistant", "content": content})

            elif msg.role == "tool":
                # Tool result message
                api_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content or "",
                            }
                        ],
                    }
                )

            else:
                api_messages.append(
                    {
                        "role": msg.role,
                        "content": msg.content or "",
                    }
                )

        return api_messages

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert tool definitions to Anthropic format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in tools
        ]

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse Anthropic API response to internal format."""
        content_text: str | None = None
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        finish_reason: str = "stop"
        if response.stop_reason == "tool_use":
            finish_reason = "tool_use"
        elif response.stop_reason == "end_turn":
            finish_reason = "stop"

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            provider="claude",
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            finish_reason=finish_reason,  # type: ignore[arg-type]
        )
