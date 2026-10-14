"""Read-only tools for checking the Agent execution and presentation pipeline."""

from datetime import datetime
from zoneinfo import ZoneInfo

from strands import tool


@tool
async def current_time(timezone: str = "Asia/Shanghai") -> dict[str, str]:
    """Get the actual current time in an IANA timezone, for example Asia/Shanghai or UTC.

    Args:
        timezone: IANA timezone identifier.
    """
    return {"timezone": timezone, "time": datetime.now(ZoneInfo(timezone)).isoformat()}
