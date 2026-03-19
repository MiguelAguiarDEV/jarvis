"""LLM provider selection and fallback routing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from jarvis.llm.base import (
    AllProvidersFailedError,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
)

if TYPE_CHECKING:
    from jarvis.tools.base import ToolDefinition

log = structlog.get_logger()

# Default priority order
DEFAULT_PRIORITY = ["claude", "chatgpt", "qwen"]


class LLMRouter:
    """Selects and falls back between LLM providers.

    Selection logic:
    1. Use explicitly requested preferred provider.
    2. If preferred is unavailable/unhealthy, fall through priority chain.
    3. Priority: Claude -> ChatGPT -> Qwen (configurable).
    4. Qwen (local) is always-available fallback.

    Does NOT retry on the same provider. Moves to next on failure.
    """

    def __init__(
        self,
        providers: dict[str, LLMProvider],
        priority: list[str] | None = None,
    ) -> None:
        self._providers = providers
        self._priority = priority or DEFAULT_PRIORITY

    @property
    def providers(self) -> dict[str, LLMProvider]:
        return dict(self._providers)

    @property
    def priority(self) -> list[str]:
        return list(self._priority)

    def get_provider(self, name: str) -> LLMProvider | None:
        """Get a specific provider by name."""
        return self._providers.get(name)

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        preferred_provider: str | None = None,
    ) -> LLMResponse:
        """Route completion to best available provider.

        Tries providers in priority order. On LLMProviderError,
        logs the failure and tries the next provider.

        Args:
            messages: Conversation history.
            tools: Available tool definitions.
            system_prompt: System-level instruction.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            preferred_provider: Override priority with specific provider.

        Returns:
            LLMResponse from the first successful provider.

        Raises:
            AllProvidersFailedError: If all providers fail.
        """
        order = self._build_order(preferred_provider)
        errors: dict[str, str] = {}

        for provider_name in order:
            provider = self._providers.get(provider_name)
            if provider is None:
                continue

            if not provider.is_available:
                log.debug("llm.router.skip_unavailable", provider=provider_name)
                continue

            try:
                log.info("llm.router.trying", provider=provider_name)
                response = await provider.complete(
                    messages=messages,
                    tools=tools,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                log.info(
                    "llm.router.success",
                    provider=provider_name,
                    model=response.model,
                    finish_reason=response.finish_reason,
                )
                return response

            except LLMProviderError as e:
                errors[provider_name] = str(e)
                log.warning(
                    "llm.router.provider_failed",
                    provider=provider_name,
                    error=str(e),
                )
                continue

        msg = f"All LLM providers failed: {errors}"
        raise AllProvidersFailedError(msg)

    def _build_order(self, preferred: str | None) -> list[str]:
        """Build provider attempt order."""
        if preferred and preferred in self._providers:
            # Put preferred first, then rest of priority
            order = [preferred]
            for p in self._priority:
                if p != preferred and p in self._providers:
                    order.append(p)
            return order
        return [p for p in self._priority if p in self._providers]

    async def health_check(self) -> dict[str, bool]:
        """Check all providers and return status map."""
        results: dict[str, bool] = {}
        for name, provider in self._providers.items():
            if not provider.is_available:
                results[name] = False
                continue
            try:
                results[name] = await provider.check_health()
            except Exception:
                results[name] = False
        return results
