"""System information tool — time, date, OS info."""

from __future__ import annotations

import platform
from datetime import UTC, datetime
from typing import Any

from jarvis.tools.base import BaseTool, ToolDefinition, ToolResult


class SystemInfoTool(BaseTool):
    """Provides current time, date, and OS information.

    Does NOT access network, credentials, or sensitive data.
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="system_info",
            description=(
                "Get current system information: time, date, timezone, "
                "OS name, OS version, hostname. Use this to answer questions "
                "about the current time, date, or system details."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "time",
                                "date",
                                "datetime",
                                "timezone",
                                "os_name",
                                "os_version",
                                "hostname",
                                "all",
                            ],
                        },
                        "description": "Which fields to return. Use 'all' for everything.",
                    }
                },
                "required": ["fields"],
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute system info query.

        Args:
            fields: List of field names to return.
        """
        fields: list[str] = kwargs.get("fields", ["all"])

        if "all" in fields:
            fields = ["time", "date", "datetime", "timezone", "os_name", "os_version", "hostname"]

        now = datetime.now(tz=UTC)
        local_now = now.astimezone()

        data: dict[str, Any] = {}

        for f in fields:
            if f == "time":
                data["time"] = local_now.strftime("%H:%M:%S")
            elif f == "date":
                data["date"] = local_now.strftime("%Y-%m-%d")
            elif f == "datetime":
                data["datetime"] = local_now.isoformat()
            elif f == "timezone":
                data["timezone"] = str(local_now.tzinfo)
                data["utc_offset"] = local_now.strftime("%z")
            elif f == "os_name":
                data["os_name"] = platform.system()
            elif f == "os_version":
                data["os_version"] = platform.version()
                data["os_release"] = platform.release()
            elif f == "hostname":
                data["hostname"] = platform.node()

        return ToolResult(
            tool_name="system_info",
            success=True,
            data=data,
        )
