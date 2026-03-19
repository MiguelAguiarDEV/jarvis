"""OpenAI ChatGPT LLM provider with OAuth PKCE support."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import openai
import structlog

from jarvis.llm.base import LLMMessage, LLMProvider, LLMProviderError, LLMResponse, ToolCall

if TYPE_CHECKING:
    from jarvis.tools.base import ToolDefinition

log = structlog.get_logger()


class ChatGPTProvider(LLMProvider):
    """OpenAI ChatGPT via official SDK.

    Auth: OAuth PKCE access token (from auth flow).
    The token is loaded at init, never passed to the LLM itself.
    """

    MODEL: str = "gpt-4o"

    def __init__(self, access_token: str, model: str | None = None) -> None:
        """Initialize with OAuth access token.

        Args:
            access_token: OAuth PKCE access token from auth flow.
            model: Model name override.
        """
        self._access_token = access_token
        self._model = model or self.MODEL
        self._client = openai.AsyncOpenAI(api_key=access_token)

    @property
    def name(self) -> str:
        return "chatgpt"

    @property
    def is_available(self) -> bool:
        return bool(self._access_token)

    async def check_health(self) -> bool:
        """Send a minimal request to verify token validity."""
        try:
            await self._client.chat.completions.create(
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
        """Send messages to ChatGPT and get a completion."""
        try:
            api_messages = self._convert_messages(messages, system_prompt)
            kwargs: dict[str, Any] = {
                "model": self._model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": api_messages,
            }

            if tools:
                kwargs["tools"] = self._convert_tools(tools)

            response = await self._client.chat.completions.create(**kwargs)
            return self._parse_response(response)

        except openai.AuthenticationError as e:
            msg = f"ChatGPT authentication failed: {e}"
            raise LLMProviderError(msg) from e
        except openai.RateLimitError as e:
            msg = f"ChatGPT rate limit exceeded: {e}"
            raise LLMProviderError(msg) from e
        except openai.APIError as e:
            msg = f"ChatGPT API error: {e}"
            raise LLMProviderError(msg) from e
        except LLMProviderError:
            raise
        except Exception as e:
            msg = f"ChatGPT unexpected error: {e}"
            raise LLMProviderError(msg) from e

    def _convert_messages(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None,
    ) -> list[dict[str, Any]]:
        """Convert internal messages to OpenAI API format."""
        api_messages: list[dict[str, Any]] = []

        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            if msg.role == "system":
                api_messages.append({"role": "system", "content": msg.content or ""})

            elif msg.role == "assistant" and msg.tool_calls:
                tool_calls_api = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
                api_msg: dict[str, Any] = {
                    "role": "assistant",
                    "tool_calls": tool_calls_api,
                }
                if msg.content:
                    api_msg["content"] = msg.content
                api_messages.append(api_msg)

            elif msg.role == "tool":
                api_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id or "",
                        "content": msg.content or "",
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
        """Convert tool definitions to OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse OpenAI API response to internal format."""
        choice = response.choices[0]
        message = choice.message

        content_text = message.content
        tool_calls: list[ToolCall] = []

        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}

                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        finish_reason = "stop"
        if choice.finish_reason == "tool_calls":
            finish_reason = "tool_use"
        elif choice.finish_reason == "stop":
            finish_reason = "stop"

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            provider="chatgpt",
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            finish_reason=finish_reason,  # type: ignore[arg-type]
        )
