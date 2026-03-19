"""Qwen LLM provider via Ollama HTTP API."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from jarvis.llm.base import LLMMessage, LLMProvider, LLMProviderError, LLMResponse, ToolCall

if TYPE_CHECKING:
    from jarvis.tools.base import ToolDefinition

log = structlog.get_logger()


class QwenProvider(LLMProvider):
    """Qwen 3.5 via Ollama HTTP API.

    Auth: None (local).
    CPU fallback — always available if Ollama is running.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3.5:9b",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=120.0)

    @property
    def name(self) -> str:
        return "qwen"

    @property
    def is_available(self) -> bool:
        # Always "available" as config — health check verifies actual connectivity
        return True

    async def check_health(self) -> bool:
        """GET /api/tags to verify Ollama is running and model is available."""
        try:
            response = await self._client.get("/api/tags")
            if response.status_code != 200:
                return False
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            # Check if our model (or a prefix match) is available
            return any(self._model in m or m.startswith(self._model.split(":")[0]) for m in models)
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
        """Send messages to Ollama and get a completion."""
        try:
            api_messages = self._convert_messages(messages, system_prompt)
            payload: dict[str, Any] = {
                "model": self._model,
                "messages": api_messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            if tools:
                payload["tools"] = self._convert_tools(tools)

            response = await self._client.post("/api/chat", json=payload)

            if response.status_code != 200:
                msg = f"Ollama returned status {response.status_code}: {response.text}"
                raise LLMProviderError(msg)

            return self._parse_response(response.json())

        except LLMProviderError:
            raise
        except httpx.ConnectError as e:
            msg = f"Cannot connect to Ollama at {self._base_url}: {e}"
            raise LLMProviderError(msg) from e
        except httpx.TimeoutException as e:
            msg = f"Ollama request timed out: {e}"
            raise LLMProviderError(msg) from e
        except Exception as e:
            msg = f"Qwen/Ollama unexpected error: {e}"
            raise LLMProviderError(msg) from e

    def _convert_messages(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None,
    ) -> list[dict[str, Any]]:
        """Convert internal messages to Ollama chat format."""
        api_messages: list[dict[str, Any]] = []

        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            if msg.role == "assistant" and msg.tool_calls:
                tool_calls_api = [
                    {
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
                api_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": tool_calls_api,
                }
                api_messages.append(api_msg)

            elif msg.role == "tool":
                api_messages.append(
                    {
                        "role": "tool",
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
        """Convert tool definitions to Ollama/OpenAI-compatible format."""
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

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse Ollama JSON response to internal format."""
        message = data.get("message", {})
        content_text = message.get("content")
        tool_calls: list[ToolCall] = []

        raw_tool_calls = message.get("tool_calls", [])
        for i, tc in enumerate(raw_tool_calls):
            func = tc.get("function", {})
            arguments = func.get("arguments", {})

            # Ollama may return arguments as string or dict
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}

            tool_calls.append(
                ToolCall(
                    id=f"qwen_call_{i}",
                    name=func.get("name", ""),
                    arguments=arguments,
                )
            )

        finish_reason = "stop"
        if tool_calls:
            finish_reason = "tool_use"

        # Ollama doesn't provide token counts in the same way
        eval_count = data.get("eval_count", 0)
        prompt_eval_count = data.get("prompt_eval_count", 0)

        return LLMResponse(
            content=content_text if content_text else None,
            tool_calls=tool_calls,
            provider="qwen",
            model=data.get("model", self._model),
            usage={
                "input_tokens": prompt_eval_count,
                "output_tokens": eval_count,
            },
            finish_reason=finish_reason,  # type: ignore[arg-type]
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
