"""Tool registry and execution router."""

from __future__ import annotations

from typing import Any

import structlog

from jarvis.tools.base import (
    BaseTool,
    ToolDefinition,
    ToolExecutionError,
    ToolNotFoundError,
    ToolResult,
)

log = structlog.get_logger()


class ToolRouter:
    """Registry and executor for tools.

    LLM sees tool definitions (schemas only).
    Router executes tools with real system access.
    LLM NEVER receives credentials or raw system handles.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool by its definition name."""
        name = tool.definition.name
        self._tools[name] = tool
        log.info("tool.registered", name=name)

    def get_definitions(self) -> list[ToolDefinition]:
        """Return all tool schemas for LLM context."""
        return [tool.definition for tool in self._tools.values()]

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given arguments.

        Args:
            tool_name: Registered tool name.
            arguments: Arguments to pass to the tool.

        Returns:
            ToolResult with execution outcome.

        Raises:
            ToolNotFoundError: If tool_name is not registered.
            ToolExecutionError: If tool raises during execution.
        """
        tool = self._tools.get(tool_name)
        if tool is None:
            msg = f"Tool '{tool_name}' not found. Available: {list(self._tools.keys())}"
            raise ToolNotFoundError(msg)

        log.info("tool.executing", name=tool_name, arguments=arguments)

        try:
            result = await tool.execute(**arguments)
            log.info("tool.executed", name=tool_name, success=result.success)
            return result
        except Exception as e:
            log.error("tool.execution_failed", name=tool_name, error=str(e))
            msg = f"Tool '{tool_name}' execution failed: {e}"
            raise ToolExecutionError(msg) from e
