"""Abstract LLM provider interface and shared data types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from jarvis.tools.base import ToolDefinition


class LLMProviderError(Exception):
    """Raised when an LLM provider operation fails."""


class AllProvidersFailedError(LLMProviderError):
    """Raised when all LLM providers in the fallback chain fail."""


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool invocation requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """A message in the conversation history."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Response from an LLM provider."""

    content: str | None
    tool_calls: list[ToolCall]
    provider: str
    model: str
    usage: dict[str, int]
    finish_reason: Literal["stop", "tool_use", "error"]


class LLMProvider(ABC):
    """Abstract interface for all LLM providers.

    Implementations MUST:
    - Accept tool definitions and return tool_calls when the model requests them.
    - Never store or log credentials in responses.
    - Raise LLMProviderError on API failures (not raw HTTP errors).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g., 'claude', 'chatgpt', 'qwen')."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether provider is configured with valid credentials."""
        ...

    @abstractmethod
    async def check_health(self) -> bool:
        """Verify provider connectivity. Returns True if healthy."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send messages and get a completion.

        Args:
            messages: Conversation history.
            tools: Available tool definitions (schemas only).
            system_prompt: System-level instruction.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.

        Returns:
            LLMResponse with content and/or tool_calls.

        Raises:
            LLMProviderError: On API failure, auth failure, rate limit, etc.
        """
        ...
