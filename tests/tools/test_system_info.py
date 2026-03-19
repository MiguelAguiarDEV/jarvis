"""Tests for system_info tool."""

from __future__ import annotations

import platform
from datetime import UTC, datetime

import pytest

from jarvis.tools.system_info import SystemInfoTool


class TestSystemInfoTool:
    """Test SystemInfoTool."""

    def test_definition(self) -> None:
        tool = SystemInfoTool()
        defn = tool.definition
        assert defn.name == "system_info"
        assert "time" in defn.description.lower()
        assert defn.parameters["required"] == ["fields"]

    @pytest.mark.asyncio
    async def test_get_time(self) -> None:
        tool = SystemInfoTool()
        result = await tool.execute(fields=["time"])
        assert result.success
        assert "time" in result.data
        # Should be HH:MM:SS format
        parts = result.data["time"].split(":")
        assert len(parts) == 3

    @pytest.mark.asyncio
    async def test_get_date(self) -> None:
        tool = SystemInfoTool()
        result = await tool.execute(fields=["date"])
        assert result.success
        assert "date" in result.data
        # Should be YYYY-MM-DD format
        today = datetime.now(tz=UTC).astimezone().strftime("%Y-%m-%d")
        assert result.data["date"] == today

    @pytest.mark.asyncio
    async def test_get_datetime(self) -> None:
        tool = SystemInfoTool()
        result = await tool.execute(fields=["datetime"])
        assert result.success
        assert "datetime" in result.data
        # Should be ISO format
        assert "T" in result.data["datetime"]

    @pytest.mark.asyncio
    async def test_get_timezone(self) -> None:
        tool = SystemInfoTool()
        result = await tool.execute(fields=["timezone"])
        assert result.success
        assert "timezone" in result.data
        assert "utc_offset" in result.data

    @pytest.mark.asyncio
    async def test_get_os_name(self) -> None:
        tool = SystemInfoTool()
        result = await tool.execute(fields=["os_name"])
        assert result.success
        assert result.data["os_name"] == platform.system()

    @pytest.mark.asyncio
    async def test_get_os_version(self) -> None:
        tool = SystemInfoTool()
        result = await tool.execute(fields=["os_version"])
        assert result.success
        assert "os_version" in result.data
        assert "os_release" in result.data

    @pytest.mark.asyncio
    async def test_get_hostname(self) -> None:
        tool = SystemInfoTool()
        result = await tool.execute(fields=["hostname"])
        assert result.success
        assert result.data["hostname"] == platform.node()

    @pytest.mark.asyncio
    async def test_get_all(self) -> None:
        tool = SystemInfoTool()
        result = await tool.execute(fields=["all"])
        assert result.success
        assert "time" in result.data
        assert "date" in result.data
        assert "os_name" in result.data
        assert "hostname" in result.data

    @pytest.mark.asyncio
    async def test_default_fields_is_all(self) -> None:
        tool = SystemInfoTool()
        result = await tool.execute()
        assert result.success
        assert "time" in result.data

    @pytest.mark.asyncio
    async def test_multiple_fields(self) -> None:
        tool = SystemInfoTool()
        result = await tool.execute(fields=["time", "os_name"])
        assert result.success
        assert "time" in result.data
        assert "os_name" in result.data
        assert "hostname" not in result.data
