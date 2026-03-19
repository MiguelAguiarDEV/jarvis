"""Tests for tool router."""

from __future__ import annotations

from typing import Any

import pytest

from jarvis.tools.base import (
    BaseTool,
    ToolDefinition,
    ToolExecutionError,
    ToolNotFoundError,
    ToolResult,
)
from jarvis.tools.router import ToolRouter


class FakeTool(BaseTool):
    """Fake tool for testing."""

    def __init__(self, name: str = "fake_tool") -> None:
        self._name = name

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self._name,
            description="A fake tool",
            parameters={"type": "object", "properties": {}},
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(tool_name=self._name, success=True, data={"echo": kwargs})


class FailingTool(BaseTool):
    """Tool that always fails."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="failing_tool",
            description="Always fails",
            parameters={"type": "object", "properties": {}},
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        msg = "intentional failure"
        raise RuntimeError(msg)


class TestToolRouter:
    """Test ToolRouter."""

    def test_register_and_count(self) -> None:
        router = ToolRouter()
        assert router.tool_count == 0

        router.register(FakeTool("tool_a"))
        assert router.tool_count == 1

        router.register(FakeTool("tool_b"))
        assert router.tool_count == 2

    def test_get_definitions(self) -> None:
        router = ToolRouter()
        router.register(FakeTool("tool_a"))
        router.register(FakeTool("tool_b"))

        defs = router.get_definitions()
        assert len(defs) == 2
        names = {d.name for d in defs}
        assert names == {"tool_a", "tool_b"}

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        router = ToolRouter()
        router.register(FakeTool("my_tool"))

        result = await router.execute("my_tool", {"key": "value"})
        assert result.success
        assert result.data == {"echo": {"key": "value"}}

    @pytest.mark.asyncio
    async def test_execute_not_found(self) -> None:
        router = ToolRouter()
        with pytest.raises(ToolNotFoundError, match="nonexistent"):
            await router.execute("nonexistent", {})

    @pytest.mark.asyncio
    async def test_execute_failure_raises_execution_error(self) -> None:
        router = ToolRouter()
        router.register(FailingTool())

        with pytest.raises(ToolExecutionError, match="intentional failure"):
            await router.execute("failing_tool", {})

    def test_empty_definitions(self) -> None:
        router = ToolRouter()
        assert router.get_definitions() == []
