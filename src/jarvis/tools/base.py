"""Tool system base classes and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger()


class ToolError(Exception):
    """Base error for tool operations."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not registered."""


class ToolExecutionError(ToolError):
    """Raised when a tool fails during execution."""


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Schema sent to LLM for tool use."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Result returned from tool execution."""

    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class BaseTool(ABC):
    """Abstract base for all tools."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return the tool's schema for LLM context."""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments."""
        ...
